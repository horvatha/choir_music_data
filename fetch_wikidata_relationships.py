"""Shared helpers/constants for fetching Wikidata data about composers:
labels, relationships (father/mother/teacher/student-of/notable student/
doctoral advisor/influenced-by), attributes (citizenship/movement/genre/
instrument/...), exact dates, and sitelinks. No `main()` here -- the
actual composer-selection entry point is `cli.py fetch composers`
(see fetch_composers.py), which imports the functions/constants below.

Writes to a JSON file only -- nothing is loaded into the database here,
that's a separate decision for later. The output file's keys double as the
"already processed" list: rerunning skips composers already in it, so this
is safe to stop/resume (e.g. across rate limits or across nationality
groups run on different days).
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

USER_AGENT = "choir_music_data-wikidata-fetch/1.0 (personal research script)"
OUTPUT_FILE = "wikidata_relationships.json"

# Every composer gets these, regardless of nationality. "ru" is here
# unconditionally (not keyed off a "Russian"/"Soviet" nationality tag like
# NATIVE_LANGUAGE_BY_NATIONALITY below) because plenty of composers who
# lived and worked under the Russian Empire or Soviet Union are tagged with
# their own ethnic nationality only (Armenian, Georgian, Ukrainian,
# Azerbaijani, Estonian, ...) with no "Soviet"/"Russian" tag anywhere to key
# off of, yet they commonly have a distinct, meaningful Russian name from
# operating in Russian as the administrative lingua franca (e.g. Aram
# Khachaturian: tagged only "Armenian", died in Moscow under Soviet
# citizenship, has a proper Russian Wikipedia name). Detecting this from
# place-of-birth/death text is unreliable (many wouldn't literally say
# "Moscow"/"Leningrad"/"Soviet"), so it's simpler and safer to just always
# ask -- Wikidata omits the key gracefully when no Russian label exists.
BASE_LABEL_LANGUAGES = ["en", "hu", "ru"]

# The languages this repo fetches translated *domain data* names in (e.g.
# instrument_names, see `cli.py fetch labels --entity instrument`) --
# distinct from BASE_LABEL_LANGUAGES above, which is about resolving a
# single display label for people/places referenced in relationships/
# attributes, not about building a full per-language translation table.
# See CLAUDE.md's "Target languages for translated names" for the source
# of this list; keep the two in sync if it changes. "en" is included in
# the fetch even though English is usually already the base/default name
# -- callers should skip writing it when it's identical to the row's
# existing name (see `cli.py load names --entity instrument`).
TARGET_LANGUAGES = ["hu", "es", "fr", "en", "de", "cs", "uk", "it", "hr", "pl", "ru", "nl"]

# Additionally ask for a composer's own native-language label, beyond the
# base "en"/"hu" every composer gets -- originally just for non-Latin
# scripts (e.g. a Chinese composer's "zh" label), later extended to
# Latin-script European languages too (Italian, French, German, ...) since
# those often differ meaningfully from the English label, especially for
# Medieval/Renaissance composers where "the English Wikipedia label" is
# itself often just a transliteration of the original-language name. Keyed
# by the nationality strings in the `nationalities` table; only one
# language per entry, so compound/ambiguous nationalities (Franco-Flemish,
# Swiss, Belgian, Frankish, Scottish) are deliberately left out rather than
# guessed at. Indian composers may natively use a script other than
# Devanagari (Tamil, Bengali, Telugu, ...) that 'hi' won't catch -- not
# attempted here.
NATIVE_LANGUAGE_BY_NATIONALITY = {
    "Hungarian": "hu",
    "Russian": "ru",
    "Soviet": "ru",
    "Ukrainian": "uk",
    "Chinese": "zh",
    "Taiwanese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
    "South Korean": "ko",
    "Indian": "hi",
    "Armenian": "hy",
    "Israeli": "he",
    "Georgian": "ka",
    "Egyptian": "ar",
    "Egypt": "ar",
    "Iraqi": "ar",
    "Syrian": "ar",
    "Lebanese": "ar",
    "Tunisian": "ar",
    "Algerian": "ar",
    "Bahraini": "ar",
    "Palestinian": "ar",
    "Iranian": "fa",
    "Persian": "fa",
    "Serbian": "sr",
    "Greek": "el",
    "Bulgarian": "bg",
    "Belarusian": "be",
    "Mongolian": "mn",
    "Macedonian": "mk",
    "Bangladeshi": "bn",
    "Thai": "th",
    # Latin-script European nationalities.
    "Italian": "it",
    "French": "fr",
    "German": "de",
    "Austrian": "de",
    "Spanish": "es",
    "Catalan": "ca",
    "Galician": "gl",
    "Occitan": "oc",
    "Polish": "pl",
    "Portuguese": "pt",
    "Dutch": "nl",
    "Flemish": "nl",
    "Netherlandish": "nl",
    "Czech": "cs",
    "Bohemian": "cs",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Croatian": "hr",
    "Danish": "da",
    "Swedish": "sv",
    "Norwegian": "no",
    "Finnish": "fi",
    "Lithuanian": "lt",
    "Latvian": "lv",
    "Estonian": "et",
    "Romanian": "ro",
    "Turkish": "tr",
}

FETCH_COMPOSER_NATIONALITIES_SQL = """
    SELECT n.name FROM composer_nationalities cn
    JOIN nationalities n ON n.id = cn.nationality_id
    WHERE cn.composer_id = %s
"""


def label_languages_for(nationalities):
    languages = list(BASE_LABEL_LANGUAGES)
    for nat in nationalities:
        lang = NATIVE_LANGUAGE_BY_NATIONALITY.get(nat)
        if lang and lang not in languages:
            languages.append(lang)
    return languages

RELATIONSHIP_PROPS = {
    "P22": "father",
    "P25": "mother",
    "P40": "child",
    "P26": "spouse",
    "P1066": "student_of",
    "P802": "notable_student",
    "P184": "doctoral_advisor",
    "P737": "influenced_by",
}

# Unlike RELATIONSHIP_PROPS (which point to other people), these point to
# countries/movements/genres/places/works/etc -- a composer's "attributes"
# rather than their relationships. P27 is Wikidata's "country of
# citizenship", which is often *plural* for anyone whose country changed
# borders/name under them without them moving (e.g. a 19th-century Hungarian
# composer may show Kingdom of Hungary, Austrian Empire, and Austria-Hungary
# all at once).
ATTRIBUTE_PROPS = {
    "P27": "citizenship",
    "P135": "movement",
    "P136": "genre",
    "P1303": "instrument",
    "P412": "voice_type",
    "P800": "notable_work",
    "P166": "award_received",
    "P19": "place_of_birth",
    "P20": "place_of_death",
    "P463": "member_of",
    "P1416": "affiliation",
    "P21": "gender",
    "P106": "occupation",
}

def use_socks_proxy(port=1080):
    """Route every socket connection *made from here on* through a local
    SOCKS5 proxy (e.g. `ssh -D <port> ...`) -- lets a second fetch instance
    exit through a different IP (the SSH server's) so it isn't sharing the
    same Wikidata/Wikipedia rate-limit bucket as one running directly.

    Must be called AFTER any Postgres connection is already open: this
    monkey-patches socket.socket globally (there's no narrower way to make
    stdlib urllib SOCKS-aware without switching HTTP libraries), so calling
    it first would route the DB connection through the tunnel too, which
    isn't wanted -- Postgres should stay direct. psycopg2 keeps using
    whatever real socket it already opened before this call; only sockets
    opened afterward (i.e. this script's own HTTP requests) are affected.

    Requires PySocks (`pip install PySocks`) -- not a dependency of the
    rest of this repo, only needed for --through-vm."""
    import socket

    import socks
    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", port)
    socket.socket = socks.socksocket


def api_get(url, params, retries=5):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 2)
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
        except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
            # Transient network blips (socket read timeouts, connection
            # resets, DNS hiccups) -- over a run of hundreds of composers
            # against two different APIs, these are expected occasionally
            # and shouldn't crash the whole run, unlike a genuine HTTP error
            # response which usually means something is actually wrong.
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 2)
            print(f"  network error ({e}), retrying in {wait}s...")
            time.sleep(wait)


def get_qid(wikilinks):
    """Try each wikilink (preferring 'en') until one resolves to a Wikidata QID."""
    ordered = sorted(wikilinks, key=lambda w: w[0] != "en")
    for language, title in ordered:
        data = api_get(
            f"https://{language}.wikipedia.org/w/api.php",
            {"action": "query", "format": "json", "prop": "pageprops",
             "titles": title, "ppprop": "wikibase_item"},
        )
        for page in data.get("query", {}).get("pages", {}).values():
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                return qid
    return None


def get_entity(qid, languages):
    data = api_get(
        "https://www.wikidata.org/w/api.php",
        {"action": "wbgetentities", "format": "json", "ids": qid,
         "props": "labels|claims|sitelinks", "languages": "|".join(languages)},
    )
    return data.get("entities", {}).get(qid)


# Wikidata site IDs are "<langcode>wiki" for the language's own Wikipedia
# (e.g. "ocwiki", "huwiki"), distinct from that language's other Wikimedia
# projects ("enwiktionary", "enwikinews", ...) which this must not match.
SITELINK_RE = re.compile(r"^([a-z]{2,3}(?:-[a-z]+)?)wiki$")


def extract_sitelinks(entity):
    """{language: article_title} for every language this composer actually
    has a Wikipedia article in -- not the same as extract_relationships'
    labels, which just give a name in that language whether or not an
    article exists there. Not filtered to `languages`: sitelinks aren't
    restricted by the API's `languages` param the way labels/descriptions
    are, and knowing about an article in a language nobody asked for is
    still useful (e.g. a composer turning out to have an Occitan article
    despite not being nationality-tagged Occitan)."""
    result = {}
    for site_id, data in entity.get("sitelinks", {}).items():
        m = SITELINK_RE.match(site_id)
        if m:
            result[m.group(1)] = data["title"]
    return result


def get_labels(qids, languages=BASE_LABEL_LANGUAGES):
    """Batch-resolve display labels for up to 50 QIDs at a time. Referenced
    people (fathers/teachers/students/...) aren't composers we have a
    nationality for, so this only asks for the base languages unless told
    otherwise.

    Always additionally requests "mul" (Wikidata's language-independent
    label, used for e.g. a person's name when it doesn't change across
    languages/scripts) -- some entities carry *only* a "mul" label and no
    "en"/"hu"/"ru" one at all (e.g. Bedřich Smetana's mother, Q140302264),
    which without this silently fell back to the raw QID as the "name"."""
    labels = {}
    qids = list(qids)
    request_languages = list(languages) + ["mul"]
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "|".join(request_languages)},
        )
        for qid, entity in data.get("entities", {}).items():
            entity_labels = entity.get("labels", {})
            preferred = entity_labels.get("en") or next(iter(entity_labels.values()), None)
            labels[qid] = preferred["value"] if preferred else qid
        time.sleep(0.3)
    return labels


def get_hu_labels(qids):
    """Batch-resolve *specifically* Hungarian labels for up to 50 QIDs at a
    time. Unlike get_labels(), which always returns something (falling
    back through en/other languages/the QID itself), this only returns a
    QID that actually has an 'hu' label on Wikidata -- a QID missing from
    the result means no Hungarian name exists there, not "not fetched
    yet", so callers can tell the two apart."""
    labels = {}
    qids = list(qids)
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "hu"},
        )
        for qid, entity in data.get("entities", {}).items():
            hu_label = entity.get("labels", {}).get("hu", {}).get("value")
            if hu_label:
                labels[qid] = hu_label
        time.sleep(0.3)
    return labels


def _not_deprecated(claim):
    """Wikidata claims carry a rank (preferred/normal/deprecated) --
    "deprecated" means editors have specifically flagged this value as
    wrong/superseded (e.g. a birth date later found to be incorrect), not
    just "less important". Every extractor in this file must skip these,
    or it'll happily pick up data Wikidata itself has already corrected."""
    return claim.get("rank") != "deprecated"


def _extract_props(entity, props):
    claims = entity.get("claims", {})
    result = {}
    for prop, key in props.items():
        values = [
            c["mainsnak"]["datavalue"]["value"]["id"]
            for c in claims.get(prop, [])
            if _not_deprecated(c)
            and "datavalue" in c.get("mainsnak", {}) and "id" in c["mainsnak"]["datavalue"]["value"]
        ]
        if values:
            result[key] = values
    return result


def extract_relationships(entity):
    return _extract_props(entity, RELATIONSHIP_PROPS)


def extract_attributes(entity):
    return _extract_props(entity, ATTRIBUTE_PROPS)


IMAGE_PROP = "P18"


def extract_image(entity):
    """{"image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Ludwig%20van%20Beethoven.jpg"}
    -- P18 (image) is a Commons media filename, a plain string
    datavalue, not an entity reference like every ATTRIBUTE_PROPS entry
    -- can't go through _extract_props (which expects value["id"]), same
    "different claim shape, keep it separate" reasoning as
    extract_dates() above. Preferred-rank claim wins when there's more
    than one, same tiebreak as extract_dates().

    Special:FilePath redirects to the actual file (302, to whichever of
    Commons' MD5-hashed upload.wikimedia.org paths it currently lives
    at) without this repo needing to compute that hash itself, and works
    unchanged for a thumbnail too (append e.g. "?width=300"). Stores the
    URL, not the bytes -- downloading is a separate, later step."""
    claims = entity.get("claims", {})
    candidates = []
    for c in claims.get(IMAGE_PROP, []):
        if not _not_deprecated(c):
            continue
        datavalue = c.get("mainsnak", {}).get("datavalue", {})
        if datavalue.get("type") != "string":
            continue
        filename = datavalue.get("value")
        if filename:
            candidates.append((c.get("rank") == "preferred", filename))
    if not candidates:
        return {}
    candidates.sort(key=lambda pair: not pair[0])
    filename = candidates[0][1]
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename)
    return {"image_url": url}


DATE_PROPS = {"P569": "birth", "P570": "death"}
WIKIDATA_DATE_RE = re.compile(r"^([+-]\d+)-(\d{2})-(\d{2})T")
WIKIDATA_YEAR_RE = re.compile(r"^([+-]\d+)-")

# Wikidata time-value precision -> this repo's date_precision enum
# (schema.sql), by the same round-number-as-range-start convention
# load_composers.py's DECADE_RE already uses for CSV text ("1650" for a
# decade means 1650-1659, not "sometime touching 1650"). 11=day,
# 10=month, 9=year all resolve to a single known year (year_upper stays
# None); 8=decade/7=century/6=millennium each get a computed upper bound.
_YEAR_PRECISION_SPANS = {9: 0, 10: 0, 11: 0, 8: 9, 7: 99, 6: 999}


def extract_dates(entity):
    """{"birth": "1756-01-27", "death": "1791-12-05", "birth_year_precision":
    {"year": 1650, "year_upper": None, "precision": "exact"}, ...}.

    "birth"/"death" are only ever set from a day-level-precision claim
    (Wikidata's time values carry their own precision flag, 11=day,
    10=month, 9=year, coarser below that) -- these feed composers.
    birth_date/death_date directly (load_birth_death_places.py), so a
    fake exact date must never be stored there for a coarser claim.

    "birth_year_precision"/"death_year_precision" are the fallback for
    composers with no day-precision claim at all -- common (see
    _YEAR_PRECISION_SPANS above): a composer whose only P569 claim is
    year/decade/century/millennium precision used to be silently
    indistinguishable here from one Wikidata has zero birth information
    for, even though the claim is real and load_composers.py's own CSV
    parser already treats an equivalent range like "1650" as usable data
    (COALESCE'd into composers.birth_year/_year_upper/_precision by
    load_birth_death_places.py, only when nothing more specific already
    won). Kept as its own dict (not folded into attributes) so it can
    never collide with the "iterating a string yields characters" bug
    class that attributes' occasional _text fields caused -- see the
    isinstance(qs, list) guard elsewhere in this file."""
    claims = entity.get("claims", {})
    result = {}
    for prop, key in DATE_PROPS.items():
        day_candidates = []
        year_candidates = []
        for c in claims.get(prop, []):
            if not _not_deprecated(c):
                continue
            datavalue = c.get("mainsnak", {}).get("datavalue", {})
            value = datavalue.get("value", {})
            if datavalue.get("type") != "time":
                continue
            precision = value.get("precision")
            preferred = c.get("rank") == "preferred"
            if precision == 11:
                m = WIKIDATA_DATE_RE.match(value.get("time", ""))
                if m:
                    year, month, day = m.groups()
                    # Even a non-deprecated, day-precision claim can still
                    # be a calendar-invalid date in practice (bad upstream
                    # data) -- validate before trusting it, same reasoning
                    # as the rank check above: don't propagate what's
                    # already wrong.
                    try:
                        date(int(year), int(month), int(day))
                    except ValueError:
                        pass
                    else:
                        day_candidates.append((preferred, f"{int(year):04d}-{month}-{day}"))
            if precision in _YEAR_PRECISION_SPANS:
                m = WIKIDATA_YEAR_RE.match(value.get("time", ""))
                if m:
                    year_candidates.append((preferred, precision, int(m.group(1))))
        if day_candidates:
            # When Wikidata has more than one day-precision claim for the
            # same property (real case found: Maddalena Laura Sirmen's P569
            # had a "normal"-rank 1735 imported from enwiki alongside a
            # "preferred"-rank 1745 sourced to BnF + Grove Music Online),
            # prefer the one Wikidata's own rank marks as preferred over a
            # merely-normal one. Falls back to the first valid claim when
            # there's no preferred one, or several -- not a guarantee of
            # correctness, just deterministic and better than ignoring rank
            # entirely.
            day_candidates.sort(key=lambda pair: not pair[0])
            result[key] = day_candidates[0][1]
        if year_candidates:
            # Same preferred-first tiebreak, then most precise (highest
            # precision number) among equally-ranked claims.
            year_candidates.sort(key=lambda t: (not t[0], -t[1]))
            _, precision, year = year_candidates[0]
            span = _YEAR_PRECISION_SPANS[precision]
            result[f"{key}_year_precision"] = {
                "year": year,
                "year_upper": year + span if span else None,
                "precision": "exact" if span == 0 else "range",
            }
    return result


def extract_coordinates(entity):
    """(latitude, longitude) from a place entity's P625 claim, or None if
    it doesn't have one (some minor/historical places don't)."""
    claims = entity.get("claims", {})
    for c in claims.get("P625", []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if value and "latitude" in value and "longitude" in value:
            return value["latitude"], value["longitude"]
    return None



"""Shared constants and pure data-extraction logic for already-fetched
Wikidata entities about composers: labels, relationships (father/mother/
teacher/student-of/notable student/doctoral advisor/influenced-by),
attributes (citizenship/movement/genre/instrument/...), exact dates, and
sitelinks. No `main()` here -- the actual composer-selection entry point
is `cli.py fetch composers` (see fetch_composers.py), which imports the
functions/constants below.

Nothing here makes a network call -- that's adapters/wikidata_api.py
(api_get, get_entity, get_qid, get_labels, get_hu_labels, use_socks_proxy)
-- every function in this file operates on an already-fetched entity dict.

Writes to a JSON file only -- nothing is loaded into the database here,
that's a separate decision for later. The output file's keys double as the
"already processed" list: rerunning skips composers already in it, so this
is safe to stop/resume (e.g. across rate limits or across nationality
groups run on different days).
"""
import re
import urllib.parse
from datetime import date

from adapters.wikidata_api import BASE_LABEL_LANGUAGES
from domain import dates

OUTPUT_FILE = "wikidata_relationships.json"

# The languages this repo fetches translated *domain data* names in (e.g.
# instrument_names, see `cli.py fetch labels --entity instrument`) --
# distinct from adapters.wikidata_api.BASE_LABEL_LANGUAGES, which is about
# resolving a single display label for people/places referenced in
# relationships/attributes, not about building a full per-language
# translation table.
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

# Wikidata's calendarmodel value on a time claim -- these two specific QIDs
# (not the general "Julian calendar"/"Gregorian calendar" Wikipedia-article
# items) are what actually appears on P569/P570 claims. See composers.
# birth_calendar/death_calendar (schema.sql) for why this matters: a date
# recorded in Julian (e.g. pre-1918 Russia, pre-1752 England, pre-1700
# Protestant Germany) can be off by 10-13 days from its Gregorian form, and
# Wikidata doesn't always carry a Julian claim even for historically-Julian
# people (Purcell's entry, checked directly, has Gregorian-only claims) --
# so this must be read per-claim, never assumed from nationality/era.
_CALENDAR_MODELS = {
    "http://www.wikidata.org/entity/Q1985727": "gregorian",
    "http://www.wikidata.org/entity/Q1985786": "julian",
}


def extract_dates(entity):
    """{"birth": "1756-01-27", "birth_calendar": "gregorian", "death":
    "1791-12-05", "death_calendar": "gregorian", "birth_year_precision":
    {"year": 1650, "year_upper": None, "precision": "exact"}, ...}.

    "birth_calendar"/"death_calendar" come from the same claim that won
    "birth"/"death" (a composer can carry claims on both calendars --
    e.g. Tchaikovsky's preferred-rank P569/P570 are both Julian, Glinka's
    preferred birth is Julian but preferred death is Gregorian -- so this
    must track whichever claim actually won, not just "any" claim). None
    when calendarmodel is missing or unrecognized, which is common --
    most claims don't need this at all.

    "birth"/"death" are only ever set from a day-level-precision claim
    (Wikidata's time values carry their own precision flag, 11=day,
    10=month, 9=year, coarser below that) -- these feed composers.
    birth_date/death_date directly (load_birth_death_places.py), so a
    fake exact date must never be stored there for a coarser claim.

    "birth_year_precision"/"death_year_precision" are the fallback for
    composers with no day-precision claim at all -- common: a composer
    whose only P569 claim is year/decade/century/millennium precision
    used to be silently indistinguishable here from one Wikidata has
    zero birth information for, even though the claim is real and
    load_composers.py's own CSV parser already treats an equivalent
    range like "1650" as usable data (COALESCE'd into composers.
    birth_year/_year_upper/_precision by load_birth_death_places.py,
    only when nothing more specific already won). Kept as its own dict
    (not folded into attributes) so it can never collide with the
    "iterating a string yields characters" bug class that attributes'
    occasional _text fields caused -- see the isinstance(qs, list) guard
    elsewhere in this file.

    The actual "what do we believe" judgment -- which claim wins when
    there's more than one, century/decade/millennium block math -- is
    domain.dates.resolve_wd_claims()/resolve_winning_claim()'s job; this
    function's own job is just translating Wikidata's JSON claim shape
    into the plain WDClaim tuples that module works with. A genuinely
    ambiguous property (domain.dates.AMBIGUOUS) is treated the same as
    "no usable claims at all" here -- neither result key gets set --
    rather than silently guessing one candidate the way this function
    used to (real cases that used to get guessed wrong: Wang Xilin/
    Q7967693's two disagreeing day-precision claims picked by sort order
    alone; Pietro Antonio Fiocco/Q771208's two *different* day-precision
    claims that are both "preferred")."""
    claims = entity.get("claims", {})
    result = {}
    for prop, key in DATE_PROPS.items():
        wd_claims = extract_time_claims(entity, prop)

        winner = dates.resolve_winning_claim(wd_claims)
        if winner is None or winner is dates.AMBIGUOUS:
            continue
        if winner.precision == 11:
            result[key] = f"{winner.year:04d}-{winner.month:02d}-{winner.day:02d}"
            result[f"{key}_calendar"] = winner.calendar
        else:
            estimate = dates.resolve_wd_claims(wd_claims)
            result[f"{key}_year_precision"] = {
                "year": estimate.year, "year_upper": estimate.year_upper, "precision": estimate.precision,
            }
    return result


def extract_time_claims(entity, prop):
    """Every non-deprecated time claim for one property (P569/P570), as
    plain domain.dates.WDClaim tuples -- the Wikidata-JSON-shape parsing
    that both extract_dates() above and verify_exact_agreeing_dates.py
    need identically, factored out so there's exactly one place that
    understands this shape (precision/rank/calendarmodel, the day-
    precision-only month/day fields, calendar-invalid date filtering)
    rather than each caller re-parsing it slightly differently."""
    result = []
    for c in entity.get("claims", {}).get(prop, []):
        if not _not_deprecated(c):
            continue
        datavalue = c.get("mainsnak", {}).get("datavalue", {})
        if datavalue.get("type") != "time":
            continue
        value = datavalue.get("value", {})
        precision = value.get("precision")
        m = WIKIDATA_YEAR_RE.match(value.get("time", ""))
        if not m:
            continue
        month = day = None
        if precision == 11:
            dm = WIKIDATA_DATE_RE.match(value.get("time", ""))
            if not dm:
                continue
            y2, mo, da = dm.groups()
            # Even a non-deprecated, day-precision claim can still be a
            # calendar-invalid date in practice (bad upstream data) --
            # validate before trusting it, don't propagate what's
            # already wrong.
            try:
                date(int(y2), int(mo), int(da))
            except ValueError:
                continue
            month, day = int(mo), int(da)
        result.append(dates.WDClaim(
            year=int(m.group(1)), month=month, day=day, precision=precision,
            rank=c.get("rank"), calendar=_CALENDAR_MODELS.get(value.get("calendarmodel")),
        ))
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



"""Fetch Wikidata relationships (father, mother, teacher/student-of,
notable student, doctoral advisor, influenced-by) and cross-language name
labels for composers, keyed by our own composer_id.

Writes to a JSON file only -- nothing is loaded into the database here,
that's a separate decision for later. The output file's keys double as the
"already processed" list: rerunning skips composers already in it, so this
is safe to stop/resume (e.g. across rate limits or across nationality
groups run on different days).

Usage:
    python3 fetch_wikidata_relationships.py Hungarian
    python3 fetch_wikidata_relationships.py Russian Soviet Ukrainian
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import psycopg2

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
# instrument_names, see fetch_instrument_names.py) -- distinct from
# BASE_LABEL_LANGUAGES above, which is about resolving a single display
# label for people/places referenced in relationships/attributes, not
# about building a full per-language translation table. See CLAUDE.md's
# "Target languages for translated names" for the source of this list;
# keep the two in sync if it changes. "en" is included in the fetch even
# though English is usually already the base/default name -- callers
# should skip writing it when it's identical to the row's existing name
# (see load_instrument_names.py).
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
}

FETCH_COMPOSERS_SQL = """
    SELECT DISTINCT c.id, c.name
    FROM composers c
    JOIN composer_nationalities cn ON cn.composer_id = c.id
    JOIN nationalities n ON n.id = cn.nationality_id
    WHERE n.name = ANY(%s)
    ORDER BY c.id
"""

FETCH_WIKILINKS_SQL = "SELECT language, title FROM composer_wikilinks WHERE composer_id = %s"


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


DATE_PROPS = {"P569": "birth", "P570": "death"}
WIKIDATA_DATE_RE = re.compile(r"^([+-]\d+)-(\d{2})-(\d{2})T")


def extract_dates(entity):
    """{"birth": "1756-01-27", "death": "1791-12-05"} -- only for claims
    with day-level precision (Wikidata's time values carry their own
    precision flag, 11=day, 10=month, 9=year, coarser below that); a
    year-only or month-only date is already covered by birth_year/
    death_year, so it's skipped here rather than stored as a fake exact
    date. Kept as its own dict (not folded into attributes) so it can never
    collide with the "iterating a string yields characters" bug class that
    attributes' occasional _text fields caused -- see the isinstance(qs,
    list) guard elsewhere in this file."""
    claims = entity.get("claims", {})
    result = {}
    for prop, key in DATE_PROPS.items():
        for c in claims.get(prop, []):
            if not _not_deprecated(c):
                continue
            datavalue = c.get("mainsnak", {}).get("datavalue", {})
            value = datavalue.get("value", {})
            if datavalue.get("type") != "time" or value.get("precision") != 11:
                continue
            m = WIKIDATA_DATE_RE.match(value.get("time", ""))
            if m:
                year, month, day = m.groups()
                # Even a non-deprecated, day-precision claim can still be a
                # calendar-invalid date in practice (bad upstream data) --
                # validate before trusting it, same reasoning as the rank
                # check just above: don't propagate what's already wrong.
                try:
                    date(int(year), int(month), int(day))
                except ValueError:
                    continue
                result[key] = f"{int(year):04d}-{month}-{day}"
                break  # first valid day-precision claim wins if there are several
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


def main():
    nationalities = sys.argv[1:]
    if not nationalities:
        print("Usage: fetch_wikidata_relationships.py <nationality> [<nationality> ...]")
        return

    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            output = json.load(f)
    except FileNotFoundError:
        output = {}
    entries = output.setdefault("composers", {})
    label_cache = output.setdefault("qid_labels", {})

    conn = psycopg2.connect()
    # autocommit: this script only reads from the DB. Without it, the first
    # SELECT below opens a transaction that isn't committed until the whole
    # (very long, API-call-bound) run finishes, holding a lock that blocks
    # any concurrent schema change (e.g. ALTER TABLE) on composers/
    # composer_wikilinks for the entire run.
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_COMPOSERS_SQL, (nationalities,))
            composers = cur.fetchall()
            print(f"{len(composers)} composers for {nationalities}")

            for composer_id, name in composers:
                key = str(composer_id)
                if key in entries:
                    continue

                cur.execute(FETCH_WIKILINKS_SQL, (composer_id,))
                wikilinks = cur.fetchall()
                if not wikilinks:
                    entries[key] = {"name": name, "qid": None, "applied_to_db": True}
                    continue

                qid = get_qid(wikilinks)
                if not qid:
                    entries[key] = {"name": name, "qid": None, "applied_to_db": True}
                    continue

                cur.execute(FETCH_COMPOSER_NATIONALITIES_SQL, (composer_id,))
                composer_nationalities = [r[0] for r in cur.fetchall()]
                languages = label_languages_for(composer_nationalities)

                entity = get_entity(qid, languages)
                if entity is None:
                    # QID resolved but the entity itself didn't come back --
                    # a Wikidata redirect (merged item, data returned under
                    # a different id than requested) or a deleted item.
                    # Recorded so a rerun doesn't keep retrying it forever.
                    entries[key] = {"name": name, "qid": qid, "applied_to_db": True}
                    print(f"  {composer_id} {name}: qid={qid} but entity not found (redirect/deleted?)")
                    continue
                labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
                relationships = extract_relationships(entity)
                attributes = extract_attributes(entity)
                sitelinks = extract_sitelinks(entity)
                dates = extract_dates(entity)
                entries[key] = {
                    "name": name, "qid": qid, "labels": labels,
                    "relationships": relationships, "attributes": attributes,
                    "sitelinks": sitelinks, "dates": dates, "applied_to_db": True,
                }
                print(f"  {composer_id} {name}: qid={qid} labels={list(labels)} "
                      f"relationships={list(relationships)} attributes={list(attributes)} "
                      f"sitelinks={list(sitelinks)}")
                time.sleep(0.3)

                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=1, sort_keys=True)

            # Some older entries' "attributes" mix in plain-string summary
            # fields alongside the QID lists (e.g. "place_of_birth_text":
            # "Tobolsk, Moscow") -- iterating a string yields its individual
            # characters, so `qs` must be checked as an actual list before
            # being folded into the QID set, or a stray batch of single
            # characters gets treated as "QIDs to resolve" (harmless on its
            # own, but corrupts the batch it shares with real QIDs).
            all_qids = {
                q for e in entries.values()
                for group in (e.get("relationships", {}), e.get("attributes", {}))
                for qs in group.values() if isinstance(qs, list)
                for q in qs
            }
            unresolved = [q for q in all_qids if q not in label_cache]
            if unresolved:
                print(f"Resolving labels for {len(unresolved)} referenced people (fathers/teachers/students/...)...")
                label_cache.update(get_labels(unresolved))
    finally:
        conn.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\n{len(entries)} composers recorded in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
"""Fetch a place's full Wikidata history: country-over-time (P17) and
official-name-over-time (P1448) claims, plus each item's own predecessor/
successor QID (P1365/P1366) when it has one, plus coordinates (P625).
Supersedes fetch_place_countries.py, which only kept a single undated P17
value per place and didn't model renames/succession at all.

This fetch stays "raw data only" -- every non-deprecated P17/P1448 claim is
cached as-is, with its rank and P580/P582 (start/end time) qualifiers when
present. Only fetches QIDs that are themselves a composer's birth/death
place -- does NOT expand into whatever a predecessor/successor points at,
since Wikidata uses P1365/P1366 for far more than "same place, renamed"
(see load_birth_death_places.py's docstring), and transitively following
it pulls in unrelated places sharing nothing but an administrative
lineage. Grouping specific QIDs into one canonical place, merging windows
into place_periods rows, and resolving each composer's birth/death place
to a specific window is load_birth_death_places.py's job, not this
script's -- same fetch/load split as the rest of this repo.

Caches into wikidata_relationships.json under:
  - "place_claims": {qid: {"p17": [...], "p1448": [...], "predecessor":
    qid|None, "successor": qid|None, "coordinates": [lat, lon]|None}}
  - "qid_labels": (shared cache, see fetch_wikidata_relationships.py) --
    extended here for any place QID not already resolved (e.g. a
    predecessor/successor QID no composer directly references).
  - "place_labels": {qid: {language: name, ...}} -- every TARGET_LANGUAGES
    (fetch_wikidata_relationships.py) label a place has on Wikidata (not
    just qid_labels' single "best" pick) -- consumed by `cli.py load names
    --entity place` to populate place_names with a real per-language
    fallback chain.
  - "country_info": {country_qid: {"name": ..., "abbr": ..., "language":
    ...}} -- "name"/"abbr" same shape as the old fetch_place_countries.py;
    "language" is the country's official language (P37), mapped to a code
    via LANGUAGE_QID_TO_CODE below, when it maps to one this repo tracks
    -- resolved for every country QID that turns up in any place's P17
    claims, consumed by load_birth_death_places.py to set each
    place_periods row's default_language.

place_claims and place_labels are both derived from the *same* live
request per place QID (props=claims|labels, one combined call -- no more
separate claims-only/labels-only passes), and the full raw entity behind
that request is also stored in the wikidata_entities Postgres DB (see
adapters/wikidata_entities_store.py) exactly the way composer entities
already are. That means a rerun can reprocess an already-fetched place
straight from that DB cache -- re-deriving place_claims/place_labels with
zero API calls -- instead of only ever being able to skip a place
entirely or re-fetch it live.

Do not run this at the same time as `cli.py fetch ...`/`cli.py backfill
...` or another backfill_*.py/fetch_*.py script -- see README.md's
"Pipeline rules" for the concurrent-cache-write hazard.

Usage:
    python3 fetch_place_history.py                      # only places missing a cached entry
    python3 fetch_place_history.py --recheck             # re-fetch every referenced place live,
                                                          # ignoring the wikidata_entities cache
    python3 fetch_place_history.py --max-age-days 30     # also refresh any place (even one
                                                          # already fully cached) whose
                                                          # wikidata_entities row is older than
                                                          # this many days -- live if not fresh
                                                          # enough there either, otherwise
                                                          # re-derived from that cached entity
"""
import re
import sys
import time

from adapters import wikidata_entities_store
from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import api_get, get_labels
from fetch_wikidata_relationships import (
    OUTPUT_FILE,
    TARGET_LANGUAGES,
    _not_deprecated,
    extract_coordinates,
)

TIME_RE = re.compile(r"^([+-]\d+)-")


def _year(time_value):
    if not time_value:
        return None
    m = TIME_RE.match(time_value.get("time", ""))
    return int(m.group(1)) if m else None


def _qualifier_year(claim, prop):
    qualifiers = claim.get("qualifiers", {}).get(prop)
    if not qualifiers:
        return None
    return _year(qualifiers[0].get("datavalue", {}).get("value"))


def extract_p17_windows(entity):
    """Every non-deprecated P17 (country) claim, with its rank and
    P580/P582 (start/end time) qualifiers when present -- unlike the old
    extract_first_qid(), this keeps *all* of them so a place's full
    country history survives, not just one arbitrary claim."""
    windows = []
    for c in entity.get("claims", {}).get("P17", []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not (isinstance(value, dict) and "id" in value):
            continue
        windows.append({
            "country_qid": value["id"],
            "start": _qualifier_year(c, "P580"),
            "end": _qualifier_year(c, "P582"),
            "rank": c.get("rank"),
        })
    return windows


def extract_p1448_windows(entity):
    """Every non-deprecated P1448 (official name) claim, same shape as
    extract_p17_windows -- most places (e.g. Moscow) have none at all,
    since their name never changed; Leningrad/St. Petersburg (Q656) has
    one per historical name per language."""
    windows = []
    for c in entity.get("claims", {}).get("P1448", []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not (isinstance(value, dict) and "text" in value):
            continue
        windows.append({
            "name": value["text"],
            "language": value.get("language"),
            "start": _qualifier_year(c, "P580"),
            "end": _qualifier_year(c, "P582"),
            "rank": c.get("rank"),
        })
    return windows


def extract_single_qid(entity, prop):
    """First non-deprecated claim's QID for a to-one property like
    P1365/P1366, preferring "preferred" rank over "normal" -- same
    reasoning as fetch_us_states.py's extract_p131."""
    preferred, normal = None, None
    for c in entity.get("claims", {}).get(prop, []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not (isinstance(value, dict) and "id" in value):
            continue
        if c.get("rank") == "preferred":
            preferred = value["id"]
        elif normal is None:
            normal = value["id"]
    return preferred or normal


# Wikidata QID -> two-letter code, for the languages a place_periods row's
# default_language can actually resolve to -- deliberately narrower than
# place_labels' TARGET_LANGUAGES fetch above: this only needs to cover a
# country's *own* official language (P37), used purely to flag whether a
# period's own recorded name is already in a Latin-script language (see
# extract_official_language below and concert_music_app's
# services/places.py) -- widening place_labels' translation coverage
# doesn't change what "the country's own language" can be. Verified
# against Wikidata directly, not from memory (Q1860/Q9067/Q7737/Q188 ==
# English/Hungarian/Russian/German respectively) -- extend this if more
# languages turn out to matter for that check.
LANGUAGE_QID_TO_CODE = {
    "Q1860": "en",
    "Q9067": "hu",
    "Q7737": "ru",
    "Q188": "de",
}


def extract_official_language(entity):
    """A country's official language (P37), mapped to one of the codes
    this repo tracks -- e.g. Soviet Union/Russia -> 'ru', German Empire/
    Weimar/Nazi Germany -> 'de'. A country can have several P37 claims
    (minority/regional languages); this takes the first non-deprecated one
    that maps to a known code, preferring "preferred" rank when present,
    same reasoning as extract_single_qid. None when no P37 claim maps to
    a language this repo tracks -- not every country's official language
    is one we fetch place names in.

    Known limitation, deliberately not worked around: genuinely
    multi-official-language countries (Switzerland: German/French/Italian/
    Romansh, all "normal" rank, no single one marked "preferred") get
    whichever *one* of their languages happens to intersect
    LANGUAGE_QID_TO_CODE -- e.g. Switzerland always resolves to 'de',
    even for a French-speaking place. Wikidata's own data doesn't
    distinguish this case from the Soviet Union's, which also lists
    Russian at "normal" rank alongside two others with no "preferred"
    marking, yet Russian is the right answer there for this repo's
    purposes (see the Kaliningrad/Königsberg example in
    load_birth_death_places.py) -- there's no rank-based signal to tell
    "one language actually dominates" apart from "several are genuinely
    co-equal" using P37 alone. Left as-is because the wrong guess is
    inert in practice: default_language is only ever consulted (see
    concert_music_app's services/places.py) when a place's own recorded
    name isn't Latin-script -- Swiss/Belgian/Canadian/Finnish place names
    always are, so the mislabeling never reaches an actual reader."""
    preferred, normal = None, None
    for c in entity.get("claims", {}).get("P37", []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not (isinstance(value, dict) and "id" in value):
            continue
        code = LANGUAGE_QID_TO_CODE.get(value["id"])
        if not code:
            continue
        if c.get("rank") == "preferred":
            preferred = code
        elif normal is None:
            normal = code
    return preferred or normal


def _apply_entity(qid, entity, place_claims, place_labels):
    """Derives this run's place_claims[qid]/place_labels[qid] from one raw
    entity -- shared by both the DB-cache-hit path and the live-fetch path
    below, so a place reprocessed straight from wikidata_entities ends up
    identical to one just fetched live."""
    coords = extract_coordinates(entity)
    place_claims[qid] = {
        "p17": extract_p17_windows(entity),
        "p1448": extract_p1448_windows(entity),
        "predecessor": extract_single_qid(entity, "P1365"),
        "successor": extract_single_qid(entity, "P1366"),
        "coordinates": list(coords) if coords else None,
    }
    # entity["labels"] is already restricted to whatever `languages` the
    # request that produced it asked for (unlike claims, Wikidata's
    # "labels" prop is filtered server-side by the languages param) -- so
    # this is only as complete as TARGET_LANGUAGES was at fetch time; a
    # future widening of that list still needs a live re-fetch, same
    # limitation composer labels already have.
    place_labels[qid] = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}


def extract_string_claim(entity, prop):
    for c in entity.get("claims", {}).get(prop, []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            return value
    return None


def main():
    recheck = "--recheck" in sys.argv
    max_age_days = None
    if "--max-age-days" in sys.argv:
        max_age_days = float(sys.argv[sys.argv.index("--max-age-days") + 1])

    data = load_cache(OUTPUT_FILE)
    entries = data["composers"]
    qid_labels = data.setdefault("qid_labels", {})
    place_claims = data.setdefault("place_claims", {})
    place_labels = data.setdefault("place_labels", {})
    country_info = data.setdefault("country_info", {})

    seed_qids = set()
    for e in entries.values():
        attributes = e.get("attributes", {})
        seed_qids.update(attributes.get("place_of_birth", []))
        seed_qids.update(attributes.get("place_of_death", []))

    if recheck:
        todo = sorted(seed_qids)
    else:
        already_complete = {q for q in seed_qids if q in place_claims and q in place_labels}
        if max_age_days is not None and already_complete:
            # Even a fully-processed place doesn't get a free pass once a
            # max age is given -- same idea as HTTP's max-age not
            # exempting a "complete" cached response from expiring.
            fresh = set(wikidata_entities_store.fetch_entities(sorted(already_complete), max_age_days=max_age_days))
            todo = sorted(q for q in seed_qids if q not in already_complete or q not in fresh)
        else:
            todo = sorted(q for q in seed_qids if q not in already_complete)
    print(f"{len(todo)} distinct places to fetch history for" + (" (rechecking all)" if recheck else ""))

    # Every already-cached-in-wikidata_entities QID in `todo` (e.g. one
    # that just aged out of max_age_days, or one whose place_claims/
    # place_labels entry predates this DB cache existing at all) gets
    # reprocessed straight from that stored raw entity -- zero API calls.
    # --recheck bypasses this entirely: every QID goes live, matching its
    # existing "ignore whatever's cached" meaning.
    cached_entities = {} if recheck else wikidata_entities_store.fetch_entities(todo, max_age_days=max_age_days)
    live_qids = [q for q in todo if q not in cached_entities]
    if cached_entities:
        print(f"  {len(cached_entities)}/{len(todo)} served from wikidata_entities cache (no API call)")
        for qid, entity in cached_entities.items():
            _apply_entity(qid, entity, place_claims, place_labels)
        save_cache(OUTPUT_FILE, data)

    for i in range(0, len(live_qids), 50):
        batch = live_qids[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "claims|labels", "languages": "|".join(TARGET_LANGUAGES)},
        )
        for qid, entity in result.get("entities", {}).items():
            wikidata_entities_store.store_entity(qid, entity)
            _apply_entity(qid, entity, place_claims, place_labels)
        time.sleep(0.3)
        print(f"  {min(i + 50, len(live_qids))}/{len(live_qids)}...")
        save_cache(OUTPUT_FILE, data)

    unresolved_labels = sorted(q for q in place_claims if q not in qid_labels)
    if unresolved_labels:
        print(f"Resolving labels for {len(unresolved_labels)} places...")
        qid_labels.update(get_labels(unresolved_labels))
        save_cache(OUTPUT_FILE, data)

    country_qids = sorted({
        w["country_qid"]
        for claims in place_claims.values()
        for w in claims.get("p17", [])
        if "language" not in country_info.get(w["country_qid"], {})
    })
    print(f"{len(country_qids)} distinct countries to resolve name/ISO code for")
    for i in range(0, len(country_qids), 50):
        batch = country_qids[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels|claims", "languages": "en"},
        )
        for qid, entity in result.get("entities", {}).items():
            label = entity.get("labels", {}).get("en", {}).get("value", qid)
            country_info[qid] = {
                "name": label, "abbr": extract_string_claim(entity, "P297"),
                "language": extract_official_language(entity),
            }
        time.sleep(0.3)
        save_cache(OUTPUT_FILE, data)

    save_cache(OUTPUT_FILE, data)
    print(f"done -- {len(place_claims)} distinct place QIDs cached")


if __name__ == "__main__":
    main()

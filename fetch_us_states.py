"""Fetch each U.S. place's state by climbing Wikidata's P131 ("located in
the administrative territorial entity") chain one hop at a time, checking
each stop's own P31 (instance of) before deciding whether to continue.

A fixed two-hop assumption (place -> county -> state) doesn't hold: a U.S.
place's direct P131 is usually its county, but sometimes an intermediate
entity above that first (e.g. a smaller entity inside a larger county,
verified via Middlesex County, MA having its own P131 pointed at from
another entity one level down) -- and a county's own P131 doesn't stop at
the state either, it continues up to the country itself (Q30), so blindly
chasing the chain overshoots past the state. The fix: at every stop, check
whether *this* entity's P31 is "state of the United States" (Q35657) --
if so, stop there; otherwise take one more P131 hop and check again.

places.state_id only ever stores the resolved *state* -- every
intermediate stop is cached (us_admin_entities, keyed by QID) purely to
avoid re-fetching the same county/intermediate entity for every place that
shares it, never written to Postgres itself.

U.S.-only for now: same property works for other countries' equivalent
divisions, but the same-named-place ambiguity problem that motivated this
is much more common in the U.S., so it's not worth fetching everywhere yet.

Do not run this at the same time as `cli.py fetch ...`/`cli.py backfill
...` or another fetch_*.py/backfill_*.py script -- see README.md's
"Pipeline rules" for the concurrent-cache-write hazard.

Usage:
    python3 fetch_us_states.py
"""

from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import api_get, get_labels
from fetch_wikidata_relationships import OUTPUT_FILE, _not_deprecated

US_QID = "Q30"
US_STATE_TYPE = "Q35657"
MAX_HOPS = 6


def extract_p31(entity):
    return sorted({
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        for c in entity.get("claims", {}).get("P31", [])
        if _not_deprecated(c)
    })


def extract_p131(entity):
    """Several non-deprecated P131 claims can coexist (e.g. Middlesex
    County, MA has 5) -- "preferred" rank beats "normal" when both are
    present, rather than picking an arbitrary one."""
    preferred, normal = [], []
    for c in entity.get("claims", {}).get("P131", []):
        if not _not_deprecated(c):
            continue
        value = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not (isinstance(value, dict) and "id" in value):
            continue
        (preferred if c.get("rank") == "preferred" else normal).append(value["id"])
    return preferred or normal


def fetch_entities(qids, entity_cache):
    todo = [q for q in qids if q not in entity_cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch), "props": "claims"},
        )
        for qid, entity in result.get("entities", {}).items():
            entity_cache[qid] = {"p31": extract_p31(entity), "p131": extract_p131(entity)}


def main():
    data = load_cache(OUTPUT_FILE)

    place_countries = data.get("place_countries", {})
    us_places = [qid for qid, country_qid in place_countries.items() if country_qid == US_QID]
    print(f"{len(us_places)} US places")

    entity_cache = data.setdefault("us_admin_entities", {})
    place_state = data.setdefault("place_state", {})

    def save():
        save_cache(OUTPUT_FILE, data)

    current = {q: q for q in us_places if q not in place_state}
    print(f"{len(current)} places still need resolving")

    for hop in range(MAX_HOPS):
        if not current:
            break
        frontier = sorted(set(current.values()) - set(entity_cache))
        if frontier:
            print(f"  hop {hop}: fetching {len(frontier)} entities...")
            fetch_entities(frontier, entity_cache)
            save()

        for place_qid, pos in list(current.items()):
            info = entity_cache.get(pos)
            if info is None:
                continue
            if US_STATE_TYPE in info["p31"]:
                place_state[place_qid] = pos
                del current[place_qid]
            elif info["p131"]:
                current[place_qid] = info["p131"][0]
            else:
                place_state[place_qid] = None
                del current[place_qid]
        save()
        print(f"  {len(place_state)} resolved, {len(current)} still climbing")

    for place_qid in current:
        place_state[place_qid] = None
    save()

    state_qids = sorted({s for s in place_state.values() if s})
    print(f"Resolving names for {len(state_qids)} distinct states...")
    state_info = data.setdefault("state_info", {})
    fresh = get_labels(state_qids, languages=["en"])
    for qid in state_qids:
        state_info[qid] = fresh.get(qid, qid)
    save()

    resolved = sum(1 for v in place_state.values() if v)
    print(f"done -- {resolved}/{len(us_places)} US places resolved to a state")


if __name__ == "__main__":
    main()

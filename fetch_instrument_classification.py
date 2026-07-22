"""Fetch data needed to sort instruments into instrument_groups (see
load_instrument_groups.py for the actual classification logic):

  - "instrument_hornbostel_sachs": {qid: code} -- Wikidata's P1762
    (Hornbostel-Sachs classification), the primary signal. It's compact,
    present on nearly every instrument, and its digits are meaningful:
    first digit 1/2/3/4/5 = idiophone/membranophone/chordophone/aerophone/
    electrophone; for aerophones, the first three digits further split
    421/422 (edge- or reed-blown, enclosed air column) from 423
    (lip-vibrated) -- i.e. woodwind vs. brass.

  - "instrument_ancestors": {qid: [ancestor_qid, ...]} -- every QID
    reachable via a bounded walk (MAX_DEPTH hops) up P279 ("subclass of").
    Used only to detect Q52954 ("keyboard instrument") membership --
    Hornbostel-Sachs has no concept of "keyboard" at all (piano is a
    struck chordophone, organ an aerophone, by sound-production
    mechanism), so this is the one case that needs the subclass graph
    instead. P279 chain depth to any given target is inconsistent across
    instruments (verified: piano/organ/harpsichord all reach "keyboard
    instrument" in 1 hop, but e.g. a reed woodwind's most detailed
    sub-branch can still not have reached "woodwind instrument" 5+ hops
    up) -- MAX_DEPTH is a pragmatic bound, not a guarantee; instruments
    that need to reach Q52954 for a correct classification are the ones
    that matter here, and all real cases checked resolve within 1-2 hops.

    Fetched breadth-first one depth level at a time across *all*
    instruments together (not instrument-by-instrument), with a shared
    QID -> parents cache -- ancestor chains overlap heavily (many
    instruments eventually share the same mid-level Wikidata classes), so
    batching this way avoids re-fetching the same QID's parents once per
    instrument that happens to reach it.

Usage:
    python3 fetch_instrument_classification.py
"""
import json
import time

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, api_get

MAX_DEPTH = 4

FETCH_INSTRUMENTS_SQL = "SELECT id, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL"


def _fetch_claims_batch(qids, props):
    result = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch), "props": "claims"},
        )
        for qid, entity in data.get("entities", {}).items():
            result[qid] = {
                prop: [
                    c["mainsnak"]["datavalue"]["value"]["id"]
                    for c in entity.get("claims", {}).get(prop, [])
                    if c["mainsnak"].get("datavalue")
                    and isinstance(c["mainsnak"]["datavalue"]["value"], dict)
                ]
                for prop in props
            }
        time.sleep(0.3)
    return result


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    hs_codes = data.setdefault("instrument_hornbostel_sachs", {})
    ancestors = data.setdefault("instrument_ancestors", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_INSTRUMENTS_SQL)
            instrument_qids = sorted({wikidata_id for _id, wikidata_id in cur.fetchall()})
    finally:
        conn.close()

    todo = [q for q in instrument_qids if q not in hs_codes or q not in ancestors]
    print(f"{len(todo)}/{len(instrument_qids)} instruments need fetching")
    if not todo:
        return

    # P1762 is a string value, not an item reference, so it can't go
    # through the item-only extraction _fetch_claims_batch does for P279
    # -- fetch it with its own pass, kept separate for that reason.
    hs_result = {}
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch), "props": "claims"},
        )
        for qid, entity in result.get("entities", {}).items():
            codes = [
                c["mainsnak"]["datavalue"]["value"]
                for c in entity.get("claims", {}).get("P1762", [])
                if c["mainsnak"].get("datavalue")
            ]
            if codes:
                hs_result[qid] = codes[0]
        time.sleep(0.3)
    hs_codes.update(hs_result)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"  {len(hs_result)} Hornbostel-Sachs codes fetched")

    # Wave-based bounded BFS up P279, shared across all instruments in
    # `todo` at once -- see module docstring.
    parents_cache = {}  # qid -> list of P279 parent qids, fetched once each
    result_ancestors = {qid: set() for qid in todo}
    frontier_by_qid = {qid: {qid} for qid in todo}  # start each walk at itself
    for depth in range(MAX_DEPTH):
        to_fetch = sorted({
            q for frontier in frontier_by_qid.values() for q in frontier
        } - parents_cache.keys())
        if not to_fetch:
            break
        print(f"  ancestor depth {depth + 1}: fetching {len(to_fetch)} QIDs...")
        fetched = _fetch_claims_batch(to_fetch, ["P279"])
        for q in to_fetch:
            parents_cache[q] = fetched.get(q, {}).get("P279", [])
        next_frontier_by_qid = {}
        for qid, frontier in frontier_by_qid.items():
            next_frontier = set()
            for q in frontier:
                next_frontier.update(parents_cache.get(q, []))
            next_frontier -= result_ancestors[qid]
            result_ancestors[qid] |= next_frontier
            if next_frontier:
                next_frontier_by_qid[qid] = next_frontier
        frontier_by_qid = next_frontier_by_qid

    for qid, found in result_ancestors.items():
        ancestors[qid] = sorted(found)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"done -- {len(hs_codes)} Hornbostel-Sachs codes, {len(ancestors)} ancestor sets cached.")


if __name__ == "__main__":
    main()
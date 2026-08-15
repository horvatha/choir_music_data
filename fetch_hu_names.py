"""Fetch Hungarian-specific names for countries, places, and works already
referenced in wikidata_relationships.json -- a country/place/work only has
one name stored today (qid_labels, or country_info's "name"), English-
preferred, with no room for a second language. This caches Hungarian
labels separately, keyed by QID, in a new top-level "hu_names" dict --
shared across all three entity kinds, since a QID's Hungarian label means
the same thing regardless of whether it's a country, a place, or a work.

Not every QID has an 'hu' label on Wikidata at all (e.g. "Slavonic Dances"
doesn't) -- those are simply absent from hu_names rather than falling back
to something else, so the loaders can tell "no Hungarian name exists"
apart from "not fetched yet".

Nothing is loaded into Postgres here -- that's `cli.py load names`
(--entity country/place/work)'s job.

Do not run this at the same time as `cli.py fetch ...`/`cli.py backfill
...` or another fetch_*.py/backfill_*.py script -- see README.md's
"Pipeline rules" for the concurrent-cache-write hazard.

Usage:
    python3 fetch_hu_names.py
"""

from adapters.json_cache import load_cache, save_cache
from fetch_wikidata_relationships import OUTPUT_FILE, get_hu_labels


def main():
    data = load_cache(OUTPUT_FILE)

    hu_names = data.setdefault("hu_names", {})

    country_qids = set(data.get("country_info", {}))

    place_qids = set(data.get("place_coordinates", {})) | set(data.get("place_countries", {}))

    work_qids = {
        q for e in data["composers"].values()
        for q in e.get("attributes", {}).get("notable_work", [])
        if isinstance(e.get("attributes", {}).get("notable_work"), list)
    }

    all_qids = country_qids | place_qids | work_qids
    todo = sorted(all_qids - set(hu_names))
    print(f"{len(country_qids)} countries, {len(place_qids)} places, {len(work_qids)} works "
          f"({len(all_qids)} distinct QIDs, {len(todo)} not yet checked for an hu label)")

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        fresh = get_hu_labels(batch)
        for qid in batch:
            hu_names[qid] = fresh.get(qid)
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        save_cache(OUTPUT_FILE, data)

    found = sum(1 for v in hu_names.values() if v)
    print(f"done -- {found}/{len(hu_names)} QIDs have an Hungarian label")


if __name__ == "__main__":
    main()

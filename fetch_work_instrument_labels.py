"""Resolve a display name (into the shared qid_labels cache) for every
instrumentation QID (Wikidata P870, from work_attributes) not already
resolved -- about 45/73 already are, from unrelated fetches that happened
to reference the same instrument QIDs (e.g. a composer's own played-
instrument claims).

Unlike `cli.py fetch labels --entity genre`/`--entity key` this doesn't
build a per-entity translation cache -- instrumentation reuses the
composers' instruments/instrument_names tables (see
load_work_instruments.py), and that table's own
`cli.py fetch labels --entity instrument` already handles translations
for every row once it exists in instruments, whatever added it. This
script only needs to get a new instrument QID a *name* good enough to
insert a row with -- same one-best-label approach load_instruments.py
already relies on qid_labels for.

Usage:
    python3 fetch_work_instrument_labels.py
"""

from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import get_labels
from fetch_wikidata_relationships import OUTPUT_FILE


def main():
    data = load_cache(OUTPUT_FILE)
    work_attributes = data.get("work_attributes", {})
    qid_labels = data.setdefault("qid_labels", {})

    qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("instrumentation", [])})
    todo = sorted(q for q in qids if q not in qid_labels)
    print(f"{len(todo)} instrumentation QIDs not yet in qid_labels")

    if todo:
        qid_labels.update(get_labels(todo))
        save_cache(OUTPUT_FILE, data)

    print("done.")


if __name__ == "__main__":
    main()

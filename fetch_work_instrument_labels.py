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
import json

from fetch_wikidata_relationships import OUTPUT_FILE, get_labels


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})
    qid_labels = data.setdefault("qid_labels", {})

    qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("instrumentation", [])})
    todo = sorted(q for q in qids if q not in qid_labels)
    print(f"{len(todo)} instrumentation QIDs not yet in qid_labels")

    if todo:
        qid_labels.update(get_labels(todo))
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print("done.")


if __name__ == "__main__":
    main()

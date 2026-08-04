"""Resolve a display name (into the shared qid_labels cache) for every
QID referenced in any composer's relationships/attributes but not yet
resolved -- same sweep fetch_wikidata_relationships.py's main() already
does at the end of a normal run, extracted as its own script since
composers loaded via fetch_missing_composers_from_relations.py/
fetch_candidate_people.py never go through that main() loop, so their
notable_work/genre/instrument/etc. QIDs need this pass run separately
before load_works.py (etc.) can resolve them to a name instead of leaving
the row skipped ("unresolved work names skipped").

Usage:
    python3 resolve_qid_labels.py
"""
import json

from fetch_wikidata_relationships import OUTPUT_FILE, get_labels

def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["composers"]
    label_cache = data.setdefault("qid_labels", {})

    # Same string-vs-list guard as fetch_wikidata_relationships.py's own
    # sweep: some older entries mix in plain-string summary fields
    # alongside the QID lists.
    all_qids = {
        q for e in entries.values()
        for group in (e.get("relationships", {}), e.get("attributes", {}))
        for qs in group.values() if isinstance(qs, list)
        for q in qs
    }
    unresolved = sorted(q for q in all_qids if q not in label_cache)
    print(f"{len(unresolved)} unresolved QIDs out of {len(all_qids)} referenced")

    if unresolved:
        label_cache.update(get_labels(unresolved))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("done.")


if __name__ == "__main__":
    main()

"""Merge a temporary JSON file's "composers" entries into the main
wikidata_relationships.json -- the second half of the split-fetch
workflow fetch_candidate_people.py's --output option supports, for
running two fetches in parallel (e.g. one direct, one through the
pyedu.hu SOCKS tunnel) without both writing the same file at once.

Only ever adds entries (new "new:<qid>" keys or, in principle, filling in
a numeric composer_id key not already present) -- never overwrites an
existing key, so it's safe to run even if the two halves' QID lists
somehow overlapped.

Usage:
    python3 merge_candidate_people.py <temp_file.json>
"""
import json
import sys

from fetch_wikidata_relationships import OUTPUT_FILE


def main():
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <temp_file.json>")
    temp_path = sys.argv[1]

    with open(temp_path, encoding="utf-8") as f:
        temp_data = json.load(f)
    temp_entries = temp_data.get("composers", {})

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.setdefault("composers", {})

    added = 0
    skipped = 0
    for key, entry in temp_entries.items():
        if key in entries:
            skipped += 1
            continue
        entries[key] = entry
        added += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Merged {added} entries from {temp_path} into {OUTPUT_FILE} ({skipped} already present, skipped).")


if __name__ == "__main__":
    main()

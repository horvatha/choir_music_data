"""Fold wikidata_relationships_vm.json (written by `cli.py fetch composers
--era ... --through-vm` -- a second instance run locally with its requests
proxied through a VM over SSH, see that flag's help text in
fetch_composers.py) back into the main wikidata_relationships.json, once
the proxied run is done.

Only adds composer keys the main file doesn't already have -- never
overwrites an existing entry, even if the VM file somehow has a different
version of the same key (shouldn't happen if the two runs were given
non-overlapping eras, but this stays safe either way rather than silently
picking one arbitrarily).

Do not run this while a fetch/backfill script is still writing to
wikidata_relationships.json -- same concurrent-write risk noted throughout
this repo's fetch_*.py/backfill_*.py scripts.

Usage:
    python3 merge_vm_fetch.py
"""

from adapters.json_cache import load_cache, save_cache
from fetch_wikidata_relationships import OUTPUT_FILE
from fetch_composers import VM_OUTPUT_FILE


def main():
    main_data = load_cache(OUTPUT_FILE)
    vm_data = load_cache(VM_OUTPUT_FILE)

    main_entries = main_data.setdefault("composers", {})
    main_labels = main_data.setdefault("qid_labels", {})

    added_composers = 0
    for key, entry in vm_data.get("composers", {}).items():
        if key not in main_entries:
            main_entries[key] = entry
            added_composers += 1

    added_labels = 0
    for qid, label in vm_data.get("qid_labels", {}).items():
        if qid not in main_labels:
            main_labels[qid] = label
            added_labels += 1

    save_cache(OUTPUT_FILE, main_data)

    print(f"Merged {added_composers} new composers and {added_labels} new labels into {OUTPUT_FILE}.")
    print(f"({VM_OUTPUT_FILE} left untouched -- safe to delete once you've confirmed the merge looks right.)")


if __name__ == "__main__":
    main()

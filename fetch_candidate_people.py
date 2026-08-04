"""Fetch full Wikidata data (all-language labels, all-language
descriptions, relationships, attributes, dates, sitelinks) for a list of
QIDs -- unlike fetch_missing_composers_from_relations.py's underlying
approach, this stores *everyone*, not just people who turn out to be
composers. Whether someone is actually a composer is a decision to make
later against the cache (see chat: the Torchi false-positive case), and
deciding that requires having fetched them in the first place -- so
storing non-composers too means the next "is this QID a composer" check
against a name that turns up again elsewhere doesn't need a re-fetch.

Entries are keyed "new:<qid>" (see fetch_new_21st_century_wikidata.py's
convention) with a "checked" flag distinguishing "fetched and confirmed
not a composer" from "not looked at yet" -- promote_new_composer_entries.py
and load_missing_composers.py only care about entries that got loaded,
this flag is for the reverse question (skip re-fetching, but also don't
mistake "no composer occupation found" for "never checked").

Supports --socks-port to route through an SSH SOCKS tunnel (see
fetch_wikidata_relationships.use_socks_proxy and this repo's pyedu.hu
reference) so two halves of a large candidate list can be fetched in
parallel from two different IPs without sharing one rate-limit bucket.
When --output is given, writes to that file instead of the main
wikidata_relationships.json -- meant for exactly that parallel-fetch case,
merged back in afterward by merge_candidate_people.py once both halves are
done and neither process is writing anymore.

Usage:
    python3 fetch_candidate_people.py <input.txt>
        [--socks-port PORT] [--output FILE]

<input.txt>: one "qid|name" per line (no header).
"""
import json
import sys

import fetch_wikidata_relationships as fwr


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(f"Usage: {sys.argv[0]} <input.txt> [--socks-port PORT] [--output FILE]")
    input_path = args[0]

    socks_port = None
    output_path = fwr.OUTPUT_FILE
    i = 1
    while i < len(args):
        if args[i] == "--socks-port":
            socks_port = int(args[i + 1])
            i += 2
        elif args[i] == "--output":
            output_path = args[i + 1]
            i += 2
        else:
            sys.exit(f"unknown argument: {args[i]}")

    qids = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            qid, name = line.rstrip("\n").split("|", 1)
            qids.append((qid, name))
    print(f"{len(qids)} QIDs in {input_path}, writing to {output_path}")

    if socks_port is not None:
        fwr.use_socks_proxy(socks_port)
        print(f"routing through SOCKS proxy on port {socks_port}")

    try:
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    entries = data.setdefault("composers", {})

    todo = [(qid, name) for qid, name in qids if f"new:{qid}" not in entries]
    print(f"{len(todo)} not yet cached")

    fetched = 0
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        ids = "|".join(qid for qid, _ in batch)
        result = fwr.api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": ids,
             "props": "labels|descriptions|claims|sitelinks"},
        )
        wd_entities = result.get("entities", {})
        for qid, name in batch:
            entity = wd_entities.get(qid)
            if entity is None:
                continue
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            descriptions = {lang: v["value"] for lang, v in entity.get("descriptions", {}).items()}
            entries[f"new:{qid}"] = {
                "name": name, "qid": qid, "labels": labels, "descriptions": descriptions,
                "relationships": fwr.extract_relationships(entity), "attributes": fwr.extract_attributes(entity),
                "dates": fwr.extract_dates(entity), "sitelinks": fwr.extract_sitelinks(entity),
                "source": input_path, "checked": True,
            }
            fetched += 1
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {fetched} newly fetched into {output_path}.")


if __name__ == "__main__":
    main()

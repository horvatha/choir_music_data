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

import click

import fetch_wikidata_relationships as fwr
from adapters.json_cache import load_cache, save_cache


def fetch(input_path, socks_port, output_path):
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
        data = load_cache(output_path)
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
        save_cache(output_path, data)

    print(f"done -- {fetched} newly fetched into {output_path}.")


@click.command("candidates")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--socks-port", type=int, default=None, help="Route requests through a local SOCKS5 proxy on this port.")
@click.option("--output", "output_path", type=click.Path(), default=None, help="Write to this file instead of the main cache (for parallel-fetch splits).")
def candidates_command(input_path, socks_port, output_path):
    """Fetch full Wikidata data for every QID in INPUT_PATH (one "qid|name" per line)."""
    fetch(input_path, socks_port, output_path or fwr.OUTPUT_FILE)


if __name__ == "__main__":
    candidates_command()

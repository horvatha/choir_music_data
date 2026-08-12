"""Patch one missing/stale field into every already-fetched composer's
entry in wikidata_relationships.json, for whichever `--field` is given.
Each field keeps its own pre-existing batch size / sleep / "still needs
this" rule / referenced-QID label-resolution scope -- these differ for
real reasons (see BACKFILL_FIELDS below and each field's original
script), not harmonized into one shape.

Do NOT run this at the same time as fetch_composers.py or another
`backfill cache` invocation -- both read the whole JSON file into memory
once and periodically write their entire copy back, so running two at
once means whichever finishes a write last silently discards the other's
progress.

Usage:
    python3 backfill_cache.py --field dates
    python3 backfill_cache.py --field dates --family   # also child/spouse, same fetch
    python3 backfill_cache.py --field sitelinks
    python3 backfill_cache.py --field attributes
    python3 backfill_cache.py --field relationships
"""
import json

import click

from fetch_wikidata_relationships import (
    OUTPUT_FILE,
    api_get,
    extract_attributes,
    extract_dates,
    extract_image,
    extract_relationships,
    extract_sitelinks,
    get_labels,
)

FAMILY_PROPS = {"P40": "child", "P26": "spouse"}


def extract_family(entity):
    claims = entity.get("claims", {})
    result = {}
    for prop, key in FAMILY_PROPS.items():
        values = [
            c["mainsnak"]["datavalue"]["value"]["id"]
            for c in claims.get(prop, [])
            if "datavalue" in c.get("mainsnak", {}) and "id" in c["mainsnak"]["datavalue"]["value"]
        ]
        if values:
            result[key] = values
    return result


def _dates_apply(e, entity, family):
    e["dates"] = extract_dates(entity)
    if family:
        e.setdefault("relationships", {}).update(extract_family(entity))


def _sitelinks_apply(e, entity, family):
    e["sitelinks"] = extract_sitelinks(entity)


def _attributes_apply(e, entity, family):
    e["attributes"] = extract_attributes(entity)
    e.update(extract_image(entity))


def _relationships_apply(e, entity, family):
    relationships = extract_relationships(entity)
    if relationships:
        e.setdefault("relationships", {}).update(relationships)


def _dates_resolve_qids(entries, todo):
    return None  # dates never resolves referenced-QID labels


def _sitelinks_resolve_qids(entries, todo):
    return None


def _attributes_resolve_qids(entries, todo):
    # unconditional overwrite every run, so scan every composer's current
    # attributes, not just this run's todo (matches backfill_wikidata_
    # attributes.py's original scope).
    return {q for e in entries.values() for qs in e.get("attributes", {}).values() for q in qs}


def _relationships_resolve_qids(entries, todo):
    # incremental (only composers missing child/spouse get re-fetched), so
    # only this run's todo can have newly-referenced QIDs -- and both
    # relationships *and* attributes are scanned, matching backfill_
    # relationships.py's original scope.
    return {
        q for _, e in todo
        for group in (e.get("relationships", {}), e.get("attributes", {}))
        for qs in group.values() if isinstance(qs, list)
        for q in qs
    }


BACKFILL_FIELDS = {
    "dates": {
        "props": "claims", "batch_size": 1, "sleep": 0.3,
        "todo": lambda cid, e: bool(e.get("qid")) and "dates" not in e,
        "apply": _dates_apply, "resolve_qids": _dates_resolve_qids,
    },
    "sitelinks": {
        "props": "sitelinks", "batch_size": 1, "sleep": 0.3,
        "todo": lambda cid, e: bool(e.get("qid")) and "sitelinks" not in e,
        "apply": _sitelinks_apply, "resolve_qids": _sitelinks_resolve_qids,
    },
    "attributes": {
        "props": "claims", "batch_size": 1, "sleep": 0.3,
        "todo": lambda cid, e: bool(e.get("qid")),  # unconditional -- ATTRIBUTE_PROPS keeps growing
        "apply": _attributes_apply, "resolve_qids": _attributes_resolve_qids,
    },
    "relationships": {
        "props": "claims", "batch_size": 50, "sleep": 0,
        "todo": lambda cid, e: bool(e.get("qid"))
                                and "child" not in e.get("relationships", {})
                                and "spouse" not in e.get("relationships", {}),
        "apply": _relationships_apply, "resolve_qids": _relationships_resolve_qids,
    },
}


def _run_one_at_a_time(todo, config, family, save_every=20):
    import time
    for i, (cid, e) in enumerate(todo):
        qid = e["qid"]
        entity_data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": qid, "props": config["props"]},
        )
        entity = entity_data.get("entities", {}).get(qid, {})
        config["apply"](e, entity, family)
        if config["sleep"]:
            time.sleep(config["sleep"])
        if (i + 1) % save_every == 0:
            print(f"  {i + 1}/{len(todo)}...")
            yield


def _run_batched(todo, config):
    batch_size = config["batch_size"]
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        qids = [e["qid"] for _, e in batch]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(qids), "props": config["props"]},
        )
        entities = result.get("entities", {})
        for cid, e in batch:
            entity = entities.get(e["qid"])
            if entity is not None:
                config["apply"](e, entity, False)
        print(f"  {min(i + batch_size, len(todo))}/{len(todo)}...")
        yield


def backfill(field, family):
    config = BACKFILL_FIELDS[field]

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["composers"]
    label_cache = data.setdefault("qid_labels", {})

    todo = [(cid, e) for cid, e in entries.items() if config["todo"](cid, e)]
    print(f"{len(todo)} composers to backfill {field} for" + (" (+ child/spouse)" if family else ""))

    runner = _run_one_at_a_time(todo, config, family) if config["batch_size"] == 1 else _run_batched(todo, config)
    for _ in runner:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    referenced_qids = config["resolve_qids"](entries, todo)
    if referenced_qids:
        unresolved = [q for q in referenced_qids if q not in label_cache]
        if unresolved:
            print(f"Resolving labels for {len(unresolved)} referenced entities...")
            label_cache.update(get_labels(unresolved))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("done")


@click.command("cache")
@click.option("--field", type=click.Choice(sorted(BACKFILL_FIELDS)), required=True, help="Which cache field to backfill.")
@click.option("--family", is_flag=True, help="With --field dates: also extract child/spouse from the same fetch.")
def cache_command(field, family):
    """Backfill --field into every already-fetched composer's cache entry.

    Do not run concurrently with fetch composers or another backfill cache
    invocation (shared read-modify-write race on the cache file).
    """
    if family and field != "dates":
        raise click.UsageError("--family is only valid with --field dates")
    backfill(field, family)


if __name__ == "__main__":
    cache_command()

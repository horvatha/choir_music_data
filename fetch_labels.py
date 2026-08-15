"""Fetch a QID -> {language: name} label cache for one entity type from
Wikidata, for whichever `--entity` is given. Two source shapes:

- instrument/country: QIDs come from that entity's own DB table
  (`WHERE wikidata_id IS NOT NULL`), fetched in TARGET_LANGUAGES only
  (see CLAUDE.md's "Target languages for translated names").
- genre/key: these don't have DB rows yet at this point (that's
  load_names.py's job, via load_genres.py/load_musical_keys.py) -- their
  QIDs come from the "form_of_creative_work"/"tonality" fields of the
  work_attributes cache fetch_work_details.py already wrote, and every
  language Wikidata has a label for is cached (not just TARGET_LANGUAGES),
  so growing that list later only needs a load rerun, not another fetch.

Caches into wikidata_relationships.json under `<entity>_labels`:
{qid: {language: name, ...}}, same shape for all four entities.

Usage:
    python3 fetch_labels.py --entity instrument            # only missing a cached entry
    python3 fetch_labels.py --entity instrument --recheck   # re-fetch every one too
    python3 fetch_labels.py --entity country
    python3 fetch_labels.py --entity genre
    python3 fetch_labels.py --entity key
"""

import click
import psycopg2

from adapters.json_cache import load_cache, save_cache
from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES, api_get

LABEL_ENTITIES = {
    "instrument": {
        "source": "db",
        "sql": "SELECT id, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL",
        "cache_key": "instrument_labels",
        "languages": TARGET_LANGUAGES,
        "plural": "instruments",
    },
    "country": {
        "source": "db",
        "sql": "SELECT id, wikidata_id FROM countries WHERE wikidata_id IS NOT NULL",
        "cache_key": "country_labels",
        "languages": TARGET_LANGUAGES,
        "plural": "countries",
    },
    "genre": {
        "source": "cache",
        "cache_qid_field": "form_of_creative_work",
        "cache_key": "genre_labels",
        "languages": None,
        "plural": "genres",
    },
    "key": {
        "source": "cache",
        "cache_qid_field": "tonality",
        "cache_key": "key_labels",
        "languages": None,
        "plural": "keys",
    },
}


def _qids_from_db(sql):
    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return sorted({wikidata_id for _id, wikidata_id in cur.fetchall()})
    finally:
        conn.close()


def _qids_from_cache(work_attributes, field):
    return sorted({q for attrs in work_attributes.values() for q in attrs.get(field, [])})


def fetch(entity, recheck):
    config = LABEL_ENTITIES[entity]

    data = load_cache(OUTPUT_FILE)
    label_cache = data.setdefault(config["cache_key"], {})

    if config["source"] == "db":
        qids = _qids_from_db(config["sql"])
    else:
        qids = _qids_from_cache(data.get("work_attributes", {}), config["cache_qid_field"])

    todo = sorted(q for q in qids if recheck or q not in label_cache)
    print(f"{len(todo)} distinct {config['plural']} to fetch names for" + (" (rechecking all)" if recheck else ""))

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        params = {"action": "wbgetentities", "format": "json", "ids": "|".join(batch), "props": "labels"}
        if config["languages"] is not None:
            params["languages"] = "|".join(config["languages"])
        result = api_get("https://www.wikidata.org/w/api.php", params)
        for qid, entity_data in result.get("entities", {}).items():
            label_cache[qid] = {lang: v["value"] for lang, v in entity_data.get("labels", {}).items()}
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        save_cache(OUTPUT_FILE, data)

    print(f"done -- {len(label_cache)} distinct {entity} QIDs cached.")


@click.command("labels")
@click.option("--entity", type=click.Choice(sorted(LABEL_ENTITIES)), required=True, help="Which entity's label cache to fetch.")
@click.option("--recheck", is_flag=True, help="Re-fetch every entity, not just ones missing a cached entry.")
def labels_command(entity, recheck):
    """Fetch a QID -> {language: name} label cache for --entity from Wikidata."""
    fetch(entity, recheck)


if __name__ == "__main__":
    labels_command()

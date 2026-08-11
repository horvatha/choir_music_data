"""Load `<entity>_names` tables from the per-entity label caches
fetch_labels.py (`cli.py fetch labels --entity ...`) and fetch_place_history.py
wrote into wikidata_relationships.json -- one row per entity per language
Wikidata actually has a label for, filtered to TARGET_LANGUAGES where the
entity's own fetch step didn't already limit itself to that set.

"en" is skipped when it's identical to the entity's own base name-column
value -- that's usually already the English label, so storing an
identical "en" row would just be redundant. Instrument has hand-fixed
NAME_OVERRIDES for QID/language pairs where two distinct instruments'
Wikidata labels collide (see the dict below for the reasoning per pair).
Place has no base name-column to compare against (a place can have more
than one QID -- see load_birth_death_places.py -- so place_qids has no
"name" of its own), so it never skips an "en" row.

upsert_entity_names() is also reused in place by load_genres.py and
load_musical_keys.py, whose genre/key ids are created earlier in the same
truncate+rebuild transaction the name loop needs -- pulling their name
step into this command would cost an extra DB round-trip for no benefit,
so those two stay standalone scripts and just call the shared loop.

Usage:
    python3 load_names.py --entity country
    python3 load_names.py --entity instrument
    python3 load_names.py --entity place
    python3 load_names.py --entity work
"""
import json

import click
import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

INSTRUMENT_NAME_OVERRIDES = {
    ("Q1588017", "hu"): "cimbalom (hangszercsalád)",  # vs Q8374 plain "cimbalom"
    ("Q1444", "hu"): "orgona (hangszercsalád)",  # vs Q281460 "pipe organ", plain "orgona"
    ("Q1444", "de"): "Orgel (Instrumentenfamilie)",  # vs Q281460 "pipe organ", plain "Orgel"
    ("Q1444", "fr"): "orgue (famille d'instruments)",  # vs Q281460 "pipe organ", plain "orgue"
    ("Q1444", "hr"): "orgulje (obitelj instrumenata)",  # vs Q281460 "pipe organ", plain "orgulje"
    ("Q1444", "uk"): "орган (сімейство інструментів)",  # vs Q281460 "pipe organ", plain "орган"
    ("Q11405", "de"): "Flöte (Instrumentenfamilie)",  # vs Q750934 "pipe", plain "Flöte"
}

NAME_ENTITIES = {
    "country": {
        "select_sql": "SELECT id, name, wikidata_id FROM countries WHERE wikidata_id IS NOT NULL",
        "cache_key": "country_labels",
        "upsert_sql": """
            INSERT INTO country_names (country_id, language, name) VALUES (%s, %s, %s)
            ON CONFLICT (country_id, language) DO UPDATE SET name = EXCLUDED.name
        """,
        "target_languages": None,
        "overrides": None,
    },
    "instrument": {
        "select_sql": "SELECT id, name, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL",
        "cache_key": "instrument_labels",
        "upsert_sql": """
            INSERT INTO instrument_names (instrument_id, language, name) VALUES (%s, %s, %s)
            ON CONFLICT (instrument_id, language) DO UPDATE SET name = EXCLUDED.name
        """,
        "target_languages": None,
        "overrides": INSTRUMENT_NAME_OVERRIDES,
    },
    "place": {
        "select_sql": "SELECT place_id, NULL, wikidata_id FROM place_qids",
        "cache_key": "place_labels",
        "upsert_sql": """
            INSERT INTO place_names (place_id, language, name) VALUES (%s, %s, %s)
            ON CONFLICT (place_id, language) DO UPDATE SET name = EXCLUDED.name
        """,
        "target_languages": None,
        "overrides": None,
    },
    "work": {
        "select_sql": "SELECT id, name, wikidata_id FROM works WHERE wikidata_id IS NOT NULL",
        "cache_key": "work_labels",
        "upsert_sql": """
            INSERT INTO work_names (work_id, language, name) VALUES (%s, %s, %s)
            ON CONFLICT (work_id, language) DO UPDATE SET name = EXCLUDED.name
        """,
        "target_languages": TARGET_LANGUAGES,
        "overrides": None,
    },
}


def upsert_entity_names(cur, upsert_sql, entity_id, wikidata_id, labels, base_name, target_languages=None, overrides=None):
    """Insert one row per (entity_id, language, name) in `labels`, skipping
    languages outside `target_languages` (when given) and a redundant "en"
    row identical to `base_name`. Returns the number of rows upserted."""
    loaded = 0
    for language, name in labels.items():
        if target_languages is not None and language not in target_languages:
            continue
        if overrides:
            name = overrides.get((wikidata_id, language), name)
        if language == "en" and name == base_name:
            continue
        cur.execute(upsert_sql, (entity_id, language, name))
        loaded += 1
    return loaded


def load(entity):
    config = NAME_ENTITIES[entity]
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    label_cache = data.get(config["cache_key"], {})

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(config["select_sql"])
                for entity_id, base_name, wikidata_id in cur.fetchall():
                    labels = label_cache.get(wikidata_id, {})
                    loaded += upsert_entity_names(
                        cur, config["upsert_sql"], entity_id, wikidata_id, labels, base_name,
                        target_languages=config["target_languages"], overrides=config["overrides"],
                    )
    finally:
        conn.close()
    print(f"Loaded {loaded} {entity} names.")


@click.command("names")
@click.option("--entity", type=click.Choice(sorted(NAME_ENTITIES)), required=True, help="Which entity's names table to load.")
def names_command(entity):
    """Load <entity>_names from the cached Wikidata labels."""
    load(entity)


if __name__ == "__main__":
    names_command()

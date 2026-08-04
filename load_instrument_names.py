"""Load instrument_names for every instrument from the "instrument_labels"
cache fetch_instrument_names.py wrote into wikidata_relationships.json --
one row per instrument per TARGET_LANGUAGES entry that Wikidata actually
has a label for.

"en" is skipped when it's identical to the instrument's own instruments.name
-- English is usually already the base/default name (see
load_instruments.py), so storing an identical "en" row would just be
redundant; it's only kept when Wikidata's English label genuinely differs
from whatever name this repo already uses for that instrument.

NAME_OVERRIDES hand-fixes cases where two distinct instruments' Wikidata
labels collide in a given language -- same pattern as load_tags.py's
NAME_OVERRIDES (see its comment). Every entry found so far follows the
same shape: a general category vs. one of its own specific subtypes
(confirmed via each pair's P279 "subclass of" claim), where the language
in question only has one common word for both, normally understood by
default to mean the specific one -- so the specific instrument keeps the
plain Wikidata label and the general category gets an "(instrument
family)" suffix, not the other way around:
  - Q8374 "cimbalom" (the specific Hungarian concert instrument, with its
    own hu Wikipedia article) vs. Q1588017 "hammered dulcimer" (the broad
    worldwide instrument family, no hu article of its own) -- both
    otherwise carry the plain Wikidata hu label "cimbalom".
  - Q281460 "pipe organ" (subclass of the next one) vs. Q1444 "organ"
    (the general category -- covers pipe, reed/harmonium, and electronic
    organs alike) -- both otherwise carry the plain Wikidata hu label
    "orgona".
  - Q750934 "pipe" (P279 subclass of the next one; Wikidata's own de
    description calls it "einfache Holzflöte", a specific simple wooden
    folk instrument) vs. Q11405 "flute" (the general woodwind-family
    category) -- both otherwise carry the plain Wikidata de label
    "Flöte".

Usage:
    python3 load_instrument_names.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

NAME_OVERRIDES = {
    ("Q1588017", "hu"): "cimbalom (hangszercsalád)",  # vs Q8374 plain "cimbalom"
    ("Q1444", "hu"): "orgona (hangszercsalád)",  # vs Q281460 "pipe organ", plain "orgona"
    ("Q11405", "de"): "Flöte (Instrumentenfamilie)",  # vs Q750934 "pipe", plain "Flöte"
}

UPSERT_INSTRUMENT_NAME_SQL = """
    INSERT INTO instrument_names (instrument_id, language, name)
    VALUES (%(instrument_id)s, %(language)s, %(name)s)
    ON CONFLICT (instrument_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    instrument_labels = data.get("instrument_labels", {})

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL")
                for instrument_id, base_name, wikidata_id in cur.fetchall():
                    for language, name in instrument_labels.get(wikidata_id, {}).items():
                        name = NAME_OVERRIDES.get((wikidata_id, language), name)
                        if language == "en" and name == base_name:
                            continue
                        cur.execute(UPSERT_INSTRUMENT_NAME_SQL, {
                            "instrument_id": instrument_id, "language": language, "name": name,
                        })
                        loaded += 1
    finally:
        conn.close()
    print(f"Loaded {loaded} instrument names.")


if __name__ == "__main__":
    load()
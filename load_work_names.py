"""Load work_names for every work from the "work_labels" cache
fetch_work_names.py wrote into wikidata_relationships.json -- one row per
work per TARGET_LANGUAGES entry that Wikidata actually has a label for.

work_labels caches *every* language Wikidata has, not just
TARGET_LANGUAGES (see fetch_work_names.py) -- this filters down to
TARGET_LANGUAGES at load time, so growing that list later just needs a
rerun of this script, no new fetch.

"en" is skipped when it's identical to the work's own works.name -- English
is usually already the base/default name (see load_works.py), so storing
an identical "en" row would just be redundant; it's only kept when
Wikidata's English label genuinely differs from whatever name this repo
already uses for that work.

Usage:
    python3 load_work_names.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

UPSERT_WORK_NAME_SQL = """
    INSERT INTO work_names (work_id, language, name)
    VALUES (%(work_id)s, %(language)s, %(name)s)
    ON CONFLICT (work_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_labels = data.get("work_labels", {})

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, base_name, wikidata_id in cur.fetchall():
                    for language, name in work_labels.get(wikidata_id, {}).items():
                        if language not in TARGET_LANGUAGES:
                            continue
                        if language == "en" and name == base_name:
                            continue
                        cur.execute(UPSERT_WORK_NAME_SQL, {
                            "work_id": work_id, "language": language, "name": name,
                        })
                        loaded += 1
    finally:
        conn.close()
    print(f"Loaded {loaded} work names.")


if __name__ == "__main__":
    load()
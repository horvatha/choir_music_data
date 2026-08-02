"""Load musical_keys/musical_key_names/work_musical_keys from the
"tonality" field (Wikidata P826) of the "work_attributes" cache, and the
"key_labels" cache fetch_key_names.py wrote -- both in
wikidata_relationships.json. Same structure as load_genres.py.

Fully rebuilds all three tables each run (truncate first) -- reruns after
a fresh fetch shouldn't leave stale links for a work whose key claim
changed upstream.

wikidata_id (not name) is the upsert key for musical_keys, same as
genres/tags -- two distinct key QIDs could in principle share a label.

Usage:
    python3 load_musical_keys.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

UPSERT_KEY_SQL = """
    INSERT INTO musical_keys (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (wikidata_id) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

UPSERT_KEY_NAME_SQL = """
    INSERT INTO musical_key_names (musical_key_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (musical_key_id, language) DO UPDATE SET name = EXCLUDED.name
"""

LINK_KEY_SQL = """
    INSERT INTO work_musical_keys (work_id, musical_key_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})
    key_labels = data.get("key_labels", {})

    key_qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("tonality", [])})

    conn = psycopg2.connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE work_musical_keys, musical_key_names, musical_keys RESTART IDENTITY CASCADE")

                key_id_by_qid = {}
                for qid in key_qids:
                    labels = key_labels.get(qid, {})
                    base_name = labels.get("en") or next(iter(labels.values()), qid)
                    cur.execute(UPSERT_KEY_SQL, (base_name, qid))
                    key_id_by_qid[qid] = cur.fetchone()[0]
                    for language, name in labels.items():
                        if language not in TARGET_LANGUAGES:
                            continue
                        if language == "en" and name == base_name:
                            continue
                        cur.execute(UPSERT_KEY_NAME_SQL, (key_id_by_qid[qid], language, name))

                links = 0
                cur.execute("SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, wikidata_id in cur.fetchall():
                    for qid in work_attributes.get(wikidata_id, {}).get("tonality", []):
                        key_id = key_id_by_qid.get(qid)
                        if key_id is None:
                            continue
                        cur.execute(LINK_KEY_SQL, (work_id, key_id))
                        links += 1
    finally:
        conn.close()
    print(f"Loaded {len(key_id_by_qid)} musical keys, {links} work-key links.")


if __name__ == "__main__":
    load()

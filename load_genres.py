"""Load genres/genre_names/work_genres from the "form_of_creative_work"
field (Wikidata P7937) of the "work_attributes" cache, and the "genre_labels"
cache `cli.py fetch labels --entity genre` wrote -- both in
wikidata_relationships.json.

Fully rebuilds all three tables each run (truncate first) -- same reasoning
as load_tags.py: reruns after a fresh fetch shouldn't leave stale links for
a work whose genre claims changed upstream.

wikidata_id (not name) is the upsert key for genres, same as tags -- two
distinct genre QIDs can share an identical English label.

"en" is skipped in genre_names when it's identical to the genre's own
genres.name -- same redundancy-avoidance as `cli.py load names` (see
load_names.py's upsert_entity_names(), which this script also calls).

Usage:
    python3 load_genres.py
"""

import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES
from load_names import upsert_entity_names

UPSERT_GENRE_SQL = """
    INSERT INTO genres (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (wikidata_id) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

UPSERT_GENRE_NAME_SQL = """
    INSERT INTO genre_names (genre_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (genre_id, language) DO UPDATE SET name = EXCLUDED.name
"""

LINK_GENRE_SQL = """
    INSERT INTO work_genres (work_id, genre_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    data = load_cache(OUTPUT_FILE)
    work_attributes = data.get("work_attributes", {})
    genre_labels = data.get("genre_labels", {})

    genre_qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("form_of_creative_work", [])})

    conn = psycopg2.connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE work_genres, genre_names, genres RESTART IDENTITY CASCADE")

                genre_id_by_qid = {}
                for qid in genre_qids:
                    labels = genre_labels.get(qid, {})
                    base_name = labels.get("en") or next(iter(labels.values()), qid)
                    cur.execute(UPSERT_GENRE_SQL, (base_name, qid))
                    genre_id_by_qid[qid] = cur.fetchone()[0]
                    upsert_entity_names(
                        cur, UPSERT_GENRE_NAME_SQL, genre_id_by_qid[qid], qid, labels, base_name,
                        target_languages=TARGET_LANGUAGES,
                    )

                links = 0
                cur.execute("SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, wikidata_id in cur.fetchall():
                    for qid in work_attributes.get(wikidata_id, {}).get("form_of_creative_work", []):
                        genre_id = genre_id_by_qid.get(qid)
                        if genre_id is None:
                            continue
                        cur.execute(LINK_GENRE_SQL, (work_id, genre_id))
                        links += 1
    finally:
        conn.close()
    print(f"Loaded {len(genre_id_by_qid)} genres, {links} work-genre links.")


if __name__ == "__main__":
    load()

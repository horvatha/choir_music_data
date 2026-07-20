"""Load place_names for every canonical place from the "place_labels"
cache fetch_place_history.py wrote into wikidata_relationships.json --
every hu/en/de/ru label a place has on Wikidata (not just one "best"
pick), so concert_music_app can offer a real per-language fallback chain
rather than showing a reader whatever script a place's period name
happened to be recorded in (e.g. Cyrillic for most Russian Empire/
Soviet-era places, unreadable to a Hungarian or English reader -- see
services/places.py's _resolve_display_name in concert_music_app).

place_labels is keyed by Wikidata QID, but places.wikidata_id moved to
place_qids (a place can now have more than one QID -- see
load_birth_death_places.py) -- so this resolves each QID to its canonical
place_id via place_qids rather than reading places.wikidata_id directly.
When a place has multiple QIDs with different cached names (e.g.
Königsberg/Kaliningrad each having their own), whichever is processed last
wins -- not worth picking one over the other for this secondary enrichment.

Usage:
    python3 load_place_names.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

UPSERT_PLACE_NAME_SQL = """
    INSERT INTO place_names (place_id, language, name)
    VALUES (%(place_id)s, %(language)s, %(name)s)
    ON CONFLICT (place_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    place_labels = data.get("place_labels", {})

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT place_id, wikidata_id FROM place_qids")
                for place_id, wikidata_id in cur.fetchall():
                    for language, name in place_labels.get(wikidata_id, {}).items():
                        cur.execute(UPSERT_PLACE_NAME_SQL, {"place_id": place_id, "language": language, "name": name})
                        loaded += 1
    finally:
        conn.close()
    print(f"Loaded {loaded} place names.")


if __name__ == "__main__":
    load()

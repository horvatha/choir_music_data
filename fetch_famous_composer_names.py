"""Fetch and load composer_alt_names for a hand-picked list of well-known
composers, restricted to TARGET_LANGUAGES only -- unlike
fetch_curated_composer_names.py (whose companion loader,
load_composer_alt_names.py, loads *every* language Wikidata has), this is
for composers whose base fetch (fetch_wikidata_relationships.py) already
covers them reasonably, where the ask was specifically "the planned
languages, not all of them".

Combines fetch and load in one script (unlike the usual fetch_*.py/
load_*.py split) since the loading logic here -- filter to
TARGET_LANGUAGES -- is one-off and specific to this composer list, not
shared with any other loader.

Usage:
    python3 fetch_famous_composer_names.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES, api_get

# Requested by name in chat; resolved to composer_id by hand against the
# composers table.
COMPOSER_IDS = {
    2490: "Maurice Ravel",
    2299: "Georges Bizet",
    2401: "Claude Debussy",
    2248: "Bedřich Smetana",
    2313: "Antonín Dvořák",
    2478: "Sergei Rachmaninoff",
    3515: "George Gershwin",
    3092: "Béla Bartók",
    3123: "Zoltán Kodály",
    2325: "Nikolai Rimsky-Korsakov",
    2305: "Pyotr Ilyich Tchaikovsky",
    2120: "Ludwig van Beethoven",
    7980: "Wolfgang Amadeus Mozart",
    7968: "Joseph Haydn",
    604: "Claudio Monteverdi",
    2214: "Giuseppe Verdi",
    2422: "Jean Sibelius",
    2176: "Johann Strauss I",
    2251: "Johann Strauss II",
    2429: "Johann Strauss III",
    2257: "Josef Strauss",
    2288: "Eduard Strauss",
    2414: "Richard Strauss",
    369: "Orlande de Lassus",
    3569: "Aaron Copland",
    2247: "Anton Bruckner",
    1410: "Antonio Vivaldi",
    1228: "Arcangelo Corelli",
    2421: "Carl Nielsen",
    3792: "Dmitri Shostakovich",
    1464: "Domenico Scarlatti",
    2322: "Edvard Grieg",
    2374: "Edward Elgar",
    2187: "Felix Mendelssohn",
    2197: "Franz Liszt",
    2159: "Franz Schubert",
    2189: "Frédéric Chopin",
    1459: "George Frideric Handel",
    1433: "Georg Philipp Telemann",
    2379: "Giacomo Puccini",
    521: "Giovanni Pierluigi da Palestrina",
    2481: "Gustav Holst",
    2391: "Gustav Mahler",
    1260: "Henry Purcell",
    3136: "Igor Stravinsky",
    2279: "Johannes Brahms",
    316: "Josquin des Prez",
    2358: "Leoš Janáček",
    2473: "Ralph Vaughan Williams",
    2212: "Richard Wagner",
    2193: "Robert Schumann",
    3339: "Sergei Prokofiev",
}

UPSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.setdefault("composers", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, wikidata_id FROM composers WHERE id = ANY(%s)",
                (list(COMPOSER_IDS),),
            )
            rows = dict(cur.fetchall())
    finally:
        conn.close()

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for composer_id, name in COMPOSER_IDS.items():
                    qid = rows.get(composer_id)
                    if not qid:
                        print(f"  skip {composer_id} ({name}): no wikidata_id")
                        continue
                    result = api_get(
                        "https://www.wikidata.org/w/api.php",
                        {"action": "wbgetentities", "format": "json", "ids": qid, "props": "labels"},
                    )
                    labels = {lang: v["value"] for lang, v in result["entities"][qid].get("labels", {}).items()}
                    entry = entries.setdefault(str(composer_id), {"applied_to_db": True})
                    entry["labels"] = labels

                    added = 0
                    for language in TARGET_LANGUAGES:
                        if language == "en":
                            continue
                        label = labels.get(language)
                        if not label:
                            continue
                        cur.execute(UPSERT_ALT_NAME_SQL, (composer_id, language, label))
                        if cur.rowcount:
                            added += 1
                    loaded += added
                    print(f"  {composer_id} ({name}): {added} target-language names added")
    finally:
        conn.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"done -- {loaded} alt names loaded across {len(COMPOSER_IDS)} composers.")


if __name__ == "__main__":
    main()

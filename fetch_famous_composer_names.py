"""Fetch and load composer_alt_names for a hand-picked list of well-known
composers, restricted to TARGET_LANGUAGES only -- unlike
`cli.py fetch composer-names --curated` (whose companion loader,
load_composer_alt_names.py, loads *every* language Wikidata has), this is
for composers whose base fetch (`cli.py fetch composers`) already covers
them reasonably, where the ask was specifically "the planned languages,
not all of them".

Combines fetch and load in one script (unlike the usual fetch_*.py/
load_*.py split) since the loading logic here -- filter to
TARGET_LANGUAGES -- is one-off and specific to this composer list, not
shared with any other loader.

Only fetches composers not already cached (same --recheck-to-override
pattern as `cli.py fetch labels`) -- COMPOSER_IDS keeps growing across
sessions, and without this every run would re-fetch everyone already
done, not just the newly-added names.

Usage:
    python3 fetch_famous_composer_names.py            # only composers missing a cached entry
    python3 fetch_famous_composer_names.py --recheck   # re-fetch everyone too
"""
import sys

import psycopg2

from adapters.json_cache import load_cache, save_cache
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
    3196: "Alban Berg",
    1279: "Alessandro Scarlatti",
    2278: "Alexander Borodin",
    2419: "Alexander Glazunov",
    2472: "Alexander Scriabin",
    3171: "Anton Webern",
    2483: "Arnold Schoenberg",
    4004: "Benjamin Britten",
    2286: "Camille Saint-Saëns",
    3448: "Carl Orff",
    1678: "Carl Philipp Emanuel Bach",
    2242: "César Franck",
    2482: "Charles Ives",
    7966: "Christoph Willibald Gluck",
    3553: "Francis Poulenc",
    1331: "François Couperin",
    2331: "Gabriel Fauré",
    2158: "Gaetano Donizetti",
    2151: "Gioachino Rossini",
    575: "Giovanni Gabrieli",
    2171: "Hector Berlioz",
    3265: "Heitor Villa-Lobos",
    1444: "Jean-Philippe Rameau",
    307: "Johannes Ockeghem",
    1230: "Johann Pachelbel",
    2175: "Mikhail Glinka",
    2298: "Mily Balakirev",
    3441: "Paul Hindemith",
    194: "Thomas Tallis",
    2163: "Vincenzo Bellini",
    209: "William Byrd",
    164: "Guillaume Dufay",
    1108: "Dieterich Buxtehude",
    1455: "Johann Sebastian Bach",
    7977: "Antonio Salieri",
    2265: "Anton Rubinstein",
    3664: "Aram Khachaturian",
    3357: "Arthur Honegger",
    2142: "Carl Maria von Weber",
    3369: "Darius Milhaud",
    2357: "Engelbert Humperdinck",
    2434: "Enrique Granados",
    2428: "Erik Satie",
    3098: "George Enescu",
    2388: "Isaac Albéniz",
    2232: "Jacques Offenbach",
    4750: "Krzysztof Penderecki",
    3596: "Kurt Weill",
    4160: "Leonard Bernstein",
    2499: "Manuel de Falla",
    2479: "Max Reger",
    2135: "Niccolò Paganini",
    2527: "Ottorino Respighi",
    2406: "Pietro Mascagni",
    2376: "Ruggero Leoncavallo",
    3895: "Samuel Barber",
    4026: "Witold Lutosławski",
}

UPSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""


def main():
    recheck = "--recheck" in sys.argv

    data = load_cache(OUTPUT_FILE)
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

    # A composer already run through this script (or
    # `cli.py fetch composer-names --curated`) has a large "labels" dict --
    # `cli.py fetch composers`'s own base fetch only ever caches
    # BASE_LABEL_LANGUAGES (3) plus one nationality-derived language, so
    # anything bigger than that can only have come from a full,
    # unrestricted "props=labels" fetch. Cheap enough that a false
    # negative (re-fetching something that didn't need it) is harmless;
    # this is just to skip the common case of re-fetching the whole list
    # every time a few new composers are added.
    already_fetched = {
        int(cid) for cid, entry in entries.items()
        if cid.isdigit() and len(entry.get("labels", {})) > 5
    }

    todo = {cid: name for cid, name in COMPOSER_IDS.items() if recheck or cid not in already_fetched}
    skipped = len(COMPOSER_IDS) - len(todo)
    print(f"{len(todo)} of {len(COMPOSER_IDS)} composers need fetching"
          + (f" ({skipped} already cached, skipped)" if skipped and not recheck else ""))

    conn = psycopg2.connect()
    loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for composer_id, name in todo.items():
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

    save_cache(OUTPUT_FILE, data)
    print(f"done -- {loaded} alt names loaded across {len(COMPOSER_IDS)} composers.")


if __name__ == "__main__":
    main()

"""Fetch each instrument's name in every target language (see CLAUDE.md's
"Target languages for translated names") from Wikidata, for instruments
that already have a wikidata_id (see load_instruments.py).

Caches into wikidata_relationships.json under "instrument_labels":
{qid: {language: name, ...}} -- same shape and same file as place_labels
(see fetch_place_history.py), just keyed by instrument QID instead of
place QID. load_instrument_names.py reads this cache and writes
instrument_names.

Usage:
    python3 fetch_instrument_names.py            # only instruments missing a cached entry
    python3 fetch_instrument_names.py --recheck   # re-fetch every instrument too
"""
import json
import sys

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES, api_get

FETCH_INSTRUMENTS_SQL = "SELECT id, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL"


def main():
    recheck = "--recheck" in sys.argv

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    instrument_labels = data.setdefault("instrument_labels", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_INSTRUMENTS_SQL)
            qids = sorted({wikidata_id for _id, wikidata_id in cur.fetchall()})
    finally:
        conn.close()

    todo = sorted(q for q in qids if recheck or q not in instrument_labels)
    print(f"{len(todo)} distinct instruments to fetch names for" + (" (rechecking all)" if recheck else ""))

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "|".join(TARGET_LANGUAGES)},
        )
        for qid, entity in result.get("entities", {}).items():
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            instrument_labels[qid] = labels
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {len(instrument_labels)} distinct instrument QIDs cached.")


if __name__ == "__main__":
    main()

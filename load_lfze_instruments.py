"""Load the manually-curated composer/instrument facts from
lfze_instruments_missing_from_wikidata.json (extracted by hand from Nagy
elodok bios, see that file's _comment) into composer_instruments, with the
supporting bio sentence + source URL recorded in instrument_references
(unlike the Wikidata-sourced facts in composer_instruments, these need a
citation -- there's no Wikidata claim backing them yet).

Unlike load_instruments.py this isn't a full rebuild -- these are extra
facts on top of the Wikidata-sourced ones, so it only inserts, never
truncates. Safe to rerun: both tables are upserted on their primary keys.

Usage:
    python3 load_lfze_instruments.py
"""
import json

import psycopg2

DATA_PATH = "lfze_instruments_missing_from_wikidata.json"
SOURCE = "lfze_nagy_elodok"

FETCH_INSTRUMENT_ID_SQL = "SELECT id FROM instruments WHERE name = %s"

LINK_INSTRUMENT_SQL = """
    INSERT INTO composer_instruments (composer_id, instrument_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""

INSERT_REFERENCE_SQL = """
    INSERT INTO instrument_references (composer_id, instrument_id, source, url, evidence)
    VALUES (%(composer_id)s, %(instrument_id)s, %(source)s, %(url)s, %(evidence)s)
    ON CONFLICT (composer_id, instrument_id, source) DO UPDATE
        SET url = EXCLUDED.url, evidence = EXCLUDED.evidence
"""


def load():
    with open(DATA_PATH, encoding="utf-8") as f:
        entries = json.load(f)["entries"]

    conn = psycopg2.connect()
    linked = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for entry in entries:
                    cur.execute(FETCH_INSTRUMENT_ID_SQL, (entry["instrument"],))
                    row = cur.fetchone()
                    if row is None:
                        print(f"  skipping {entry['composer_name']} -> {entry['instrument']}: no such instrument in DB")
                        continue
                    instrument_id = row[0]
                    cur.execute(LINK_INSTRUMENT_SQL, (entry["composer_id"], instrument_id))
                    cur.execute(INSERT_REFERENCE_SQL, {
                        "composer_id": entry["composer_id"], "instrument_id": instrument_id,
                        "source": SOURCE, "url": entry["source_url"], "evidence": entry["evidence"],
                    })
                    linked += 1
    finally:
        conn.close()
    print(f"Linked {linked} composer/instrument pairs (with references) from {DATA_PATH}.")


if __name__ == "__main__":
    load()
"""Load work_instruments from the "instrumentation" field (Wikidata P870)
of the "work_attributes" cache, reusing the composers' instruments table
rather than a separate one -- most instrument QIDs referenced here (38/73)
already exist there. New ones are inserted with the same (name-is-the-
upsert-key) convention load_instruments.py uses, via qid_labels (see
fetch_work_instrument_labels.py).

Run order matters:
1. load_instruments.py (if it needs rerunning at all -- it TRUNCATEs the
   whole instruments table, which would cascade-delete work_instruments)
2. this script -- adds any new instrument rows work_attributes needs,
   plus the work_instruments links
3. `cli.py fetch labels --entity instrument` -- picks up translations for
   newly-added instrument rows automatically (it's incremental, scans the
   whole instruments table for anything not yet cached)
4. `cli.py load names --entity instrument`
5. load_instrument_groups.py -- step 1's TRUNCATE also clears every
   instrument's group_id (a plain column on the truncated-and-reinserted
   row, not preserved by the upsert), so group assignments need
   reassigning too, not just names/links

Not incremental itself -- truncates work_instruments first (not
instruments, which this only adds to, never removes from, since other
things may already reference existing rows).

Usage:
    python3 load_work_instruments.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

UPSERT_INSTRUMENT_SQL = """
    INSERT INTO instruments (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (name) DO UPDATE
        SET wikidata_id = COALESCE(instruments.wikidata_id, EXCLUDED.wikidata_id)
    RETURNING id
"""

LINK_WORK_INSTRUMENT_SQL = """
    INSERT INTO work_instruments (work_id, instrument_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})
    qid_labels = data.get("qid_labels", {})

    conn = psycopg2.connect()
    links = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE work_instruments")

                instrument_id_by_qid = {}
                cur.execute("SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, wikidata_id in cur.fetchall():
                    for qid in work_attributes.get(wikidata_id, {}).get("instrumentation", []):
                        if qid not in instrument_id_by_qid:
                            name = qid_labels.get(qid, qid)
                            cur.execute(UPSERT_INSTRUMENT_SQL, (name, qid))
                            instrument_id_by_qid[qid] = cur.fetchone()[0]
                        cur.execute(LINK_WORK_INSTRUMENT_SQL, (work_id, instrument_id_by_qid[qid]))
                        links += 1
    finally:
        conn.close()
    print(f"Loaded {len(instrument_id_by_qid)} distinct instruments, {links} work-instrument links.")


if __name__ == "__main__":
    load()

"""Load instruments/composer_instruments from the "instrument" (P1303)
attribute already fetched into wikidata_relationships.json by
`cli.py fetch composers` / `cli.py backfill cache --field attributes`.

Unlike load_nationalities.py there's no free-text parsing here -- each
attribute value is already a clean Wikidata QID, resolved to a name via the
file's qid_labels cache. instruments.name is the upsert key (not
wikidata_id), since wikidata_id is nullable -- an instrument added by hand
later with no QID still needs a stable identity to merge onto.
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

LOG_FILE = "data.log"
LOG_BATCH_SIZE = 10

UPSERT_INSTRUMENT_SQL = """
    INSERT INTO instruments (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (name) DO UPDATE
        SET wikidata_id = COALESCE(instruments.wikidata_id, EXCLUDED.wikidata_id)
    RETURNING id
"""

LINK_INSTRUMENT_SQL = """
    INSERT INTO composer_instruments (composer_id, instrument_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    """Fully rebuilds instruments/composer_instruments from
    wikidata_relationships.json (read once, up front -- the whole run works
    off that single snapshot, no re-reading mid-loop). Not incremental --
    truncates first, so reruns after a fresh fetch don't leave stale links
    for composers whose instrument list changed upstream.

    Logs the name of every composer an instrument was loaded for to
    data.log, in batches of LOG_BATCH_SIZE per line (overwritten each run,
    so it always reflects the most recent load, matching the truncate-and-
    rebuild behavior above)."""
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    qid_labels = data.get("qid_labels", {})

    conn = psycopg2.connect()
    processed = 0
    stale = 0
    logged_names = []
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as log:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE composer_instruments, instruments RESTART IDENTITY CASCADE")
                    cur.execute("SELECT id FROM composers")
                    real_composer_ids = {r[0] for r in cur.fetchall()}
                    for composer_id, entry in data["composers"].items():
                        if not entry.get("applied_to_db"):
                            # Not yet merged into the composers table (e.g. a
                            # "new:<slug>" candidate) -- composer_id isn't a
                            # real composers.id yet, so there's nothing to link.
                            continue
                        if not composer_id.isdigit() or int(composer_id) not in real_composer_ids:
                            # Stale cache id -- see README.md's "Pipeline
                            # rules" (stale cache ids after a merge).
                            stale += 1
                            continue
                        instrument_qids = entry.get("attributes", {}).get("instrument", [])
                        if not instrument_qids:
                            continue
                        processed += 1
                        for qid in instrument_qids:
                            name = qid_labels.get(qid, qid)
                            cur.execute(UPSERT_INSTRUMENT_SQL, (name, qid))
                            instrument_id = cur.fetchone()[0]
                            cur.execute(LINK_INSTRUMENT_SQL, (int(composer_id), instrument_id))

                        logged_names.append(entry.get("name", composer_id))
                        if len(logged_names) == LOG_BATCH_SIZE:
                            log.write(", ".join(logged_names) + "\n")
                            logged_names.clear()

                    if logged_names:
                        log.write(", ".join(logged_names) + "\n")
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one instrument"
          + (f", skipped {stale} stale cache entries" if stale else "")
          + f". See {LOG_FILE} for names.")


if __name__ == "__main__":
    load()
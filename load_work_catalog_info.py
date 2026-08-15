"""Load works.catalog_code and works.cpdl_id from the "catalog_code"
(P528) and "cpdl_id" (P2000) fields of the "work_attributes" cache
fetch_work_details.py wrote into wikidata_relationships.json. Both are
plain strings -- no QID resolution needed, unlike genres/dates/keys/
instruments.

A work can carry more than one catalog_code statement (e.g. a set with a
range like "BWV 525-530" plus an individual number) -- the first one found
is used, same tradeoff as load_work_dates.py's date fields.

Usage:
    python3 load_work_catalog_info.py
"""

import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

UPDATE_WORK_CATALOG_INFO_SQL = """
    UPDATE works SET catalog_code = %s, cpdl_id = %s WHERE id = %s
"""


def load():
    data = load_cache(OUTPUT_FILE)
    work_attributes = data.get("work_attributes", {})

    conn = psycopg2.connect()
    catalog_loaded = 0
    cpdl_loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, wikidata_id in cur.fetchall():
                    attrs = work_attributes.get(wikidata_id)
                    if not attrs:
                        continue
                    catalog_codes = attrs.get("catalog_code")
                    cpdl_ids = attrs.get("cpdl_id")
                    if not catalog_codes and not cpdl_ids:
                        continue
                    catalog_code = catalog_codes[0] if catalog_codes else None
                    cpdl_id = cpdl_ids[0] if cpdl_ids else None
                    if catalog_code:
                        catalog_loaded += 1
                    if cpdl_id:
                        cpdl_loaded += 1
                    cur.execute(UPDATE_WORK_CATALOG_INFO_SQL, (catalog_code, cpdl_id, work_id))
    finally:
        conn.close()
    print(f"Loaded {catalog_loaded} catalog codes, {cpdl_loaded} CPDL IDs.")


if __name__ == "__main__":
    load()

"""Load tag_wikilinks from the "tag_sitelinks" cache fetch_tag_wikilinks.py
writes into wikidata_relationships.json. Separate step, not folded into
fetch_tag_wikilinks.py itself, same split as fetch_wikidata_relationships.py
(fetch) vs. load_composers.py/load_missing_wikilinks.py (load) elsewhere in
this pipeline.

Looked up by tag wikidata_id, not tag_id: load_tags.py TRUNCATEs both
tags and composer_tags (RESTART IDENTITY) on every run, so a tag's
internal id isn't stable across reruns -- this must be rerun after every
load_tags.py run to repopulate tag_wikilinks, same as
load_missing_wikilinks.py is rerun after composers change.

Usage:
    python3 load_tag_wikilinks.py
"""
import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

INSERT_TAG_WIKILINK_SQL = """
    INSERT INTO tag_wikilinks (tag_id, language, title)
    VALUES (%s, %s, %s)
    ON CONFLICT DO NOTHING
"""


def main():
    data = load_cache(OUTPUT_FILE)
    tag_sitelinks = data.get("tag_sitelinks", {})

    conn = psycopg2.connect()
    inserted = 0
    tags_touched = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, wikidata_id FROM tags WHERE wikidata_id IS NOT NULL")
                tag_id_by_qid = {qid: tag_id for tag_id, qid in cur.fetchall()}

                for qid, sitelinks in tag_sitelinks.items():
                    tag_id = tag_id_by_qid.get(qid)
                    if tag_id is None or not sitelinks:
                        continue
                    touched = False
                    for language, title in sitelinks.items():
                        cur.execute(INSERT_TAG_WIKILINK_SQL, (tag_id, language, title))
                        if cur.rowcount:
                            inserted += 1
                            touched = True
                    if touched:
                        tags_touched += 1
    finally:
        conn.close()

    print(f"Inserted {inserted} wikilinks for {tags_touched} tags.")


if __name__ == "__main__":
    main()

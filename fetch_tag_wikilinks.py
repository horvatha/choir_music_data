"""Fetch each tag's own Wikidata sitelinks -- which language Wikipedia
editions have an article about the movement/style itself (e.g. "ars
antiqua"), as opposed to composer_wikilinks, which is a composer's own
article. Tags are sourced from composers' own {{P|135}} claims
(load_tags.py), so unlike composers, a tag's own Wikidata item is never
fetched as a full entity anywhere else in this pipeline -- get_labels()
(used for qid_labels) only ever asks for labels, not sitelinks.

Cached into wikidata_relationships.json under a new top-level
"tag_sitelinks" key ({qid: {language: title}}), same file/shape
convention as everything else fetched by this pipeline -- not a new file,
since one already exists and this is a small, one-off addition to it.
Resumable: only QIDs not already in the cache get fetched.

Usage:
    python3 fetch_tag_wikilinks.py
"""
import time

import psycopg2

from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import BASE_LABEL_LANGUAGES, get_entity
from fetch_wikidata_relationships import OUTPUT_FILE, extract_sitelinks


def main():
    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT wikidata_id FROM tags WHERE wikidata_id IS NOT NULL")
            tag_qids = sorted(r[0] for r in cur.fetchall())
    finally:
        conn.close()

    data = load_cache(OUTPUT_FILE)
    tag_sitelinks = data.setdefault("tag_sitelinks", {})

    todo = [q for q in tag_qids if q not in tag_sitelinks]
    print(f"{len(todo)} tags not yet fetched, out of {len(tag_qids)} total")

    fetched = 0
    for qid in todo:
        entity = get_entity(qid, BASE_LABEL_LANGUAGES, max_age_days=30)
        tag_sitelinks[qid] = extract_sitelinks(entity) if entity else {}
        fetched += 1
        if fetched % 20 == 0:
            save_cache(OUTPUT_FILE, data)
            print(f"...{fetched}/{len(todo)}")
        time.sleep(0.3)

    if todo:
        save_cache(OUTPUT_FILE, data)
    print(f"Fetched sitelinks for {fetched} tags.")


if __name__ == "__main__":
    main()

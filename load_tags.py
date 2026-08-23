"""Load tags/composer_tags from the "movement" (P135) attribute already
fetched into wikidata_relationships.json by fetch_wikidata_relationships.py.
See schema.sql's comment on the tags table for why this repo calls
Wikidata's "movement" property "tags" instead.

Unlike load_instruments.py, wikidata_id (not name) is the upsert key here --
two distinct Wikidata items can share the identical English label (e.g.
Q2426218 and Q878985 both label as plain "modernism"), so name alone would
silently merge unrelated tags together.

Which raw QIDs become tags, what they're named, and which composer/tag
pairs Wikidata itself is missing are all decided in domain/tags.py, not
here -- this script only does the DB I/O (TRUNCATE/SELECT/INSERT) and
reads the cache's already-fetched shape (entry["attributes"]["movement"]).
"""

import psycopg2

from adapters.json_cache import load_cache
from domain.tags import MANUAL_COMPOSER_TAGS, resolve_tag_name, resolve_tag_qids
from fetch_wikidata_relationships import OUTPUT_FILE

UPSERT_TAG_SQL = """
    INSERT INTO tags (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (wikidata_id) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

LINK_TAG_SQL = """
    INSERT INTO composer_tags (composer_id, tag_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""

INSERT_TAG_WIKILINK_SQL = """
    INSERT INTO tag_wikilinks (tag_id, language, title)
    VALUES (%s, %s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    """Fully rebuilds tags/composer_tags from wikidata_relationships.json,
    then reloads tag_wikilinks (a tag's own Wikipedia article per
    language, from fetch_tag_wikilinks.py's "tag_sitelinks" cache) in the
    same run -- TRUNCATE ... CASCADE above wipes tag_wikilinks too (it
    references tags.id), so relying on load_tag_wikilinks.py as a separate
    manual step meant it kept getting silently forgotten. The two scripts
    were unified into one for exactly this reason; fetch_tag_wikilinks.py
    (the network-fetching half) stays separate, same fetch/load split as
    everywhere else in this pipeline.

    Not incremental -- truncates first, so reruns after a fresh fetch don't
    leave stale links for composers whose recorded tags changed upstream."""
    data = load_cache(OUTPUT_FILE)
    qid_labels = data.get("qid_labels", {})
    tag_sitelinks = data.get("tag_sitelinks", {})

    conn = psycopg2.connect()
    processed = 0
    stale = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_tags, tags RESTART IDENTITY CASCADE")
                cur.execute("SELECT id FROM composers")
                real_composer_ids = {r[0] for r in cur.fetchall()}
                for composer_id, entry in data["composers"].items():
                    if not entry.get("applied_to_db"):
                        continue
                    if not composer_id.isdigit() or int(composer_id) not in real_composer_ids:
                        # Stale cache id -- see README.md's "Pipeline
                        # rules" (stale cache ids after a merge).
                        stale += 1
                        continue
                    tag_qids = entry.get("attributes", {}).get("movement", [])
                    if not tag_qids:
                        continue
                    processed += 1
                    for qid in resolve_tag_qids(tag_qids):
                        name = resolve_tag_name(qid, qid_labels)
                        cur.execute(UPSERT_TAG_SQL, (name, qid))
                        tag_id = cur.fetchone()[0]
                        cur.execute(LINK_TAG_SQL, (int(composer_id), tag_id))

                cur.execute("SELECT id, wikidata_id FROM composers WHERE wikidata_id IS NOT NULL")
                composer_id_by_qid = {qid: cid for cid, qid in cur.fetchall()}
                manual_added = 0
                manual_skipped = 0
                for composer_qid, tag_qids in MANUAL_COMPOSER_TAGS.items():
                    composer_id = composer_id_by_qid.get(composer_qid)
                    if composer_id is None:
                        manual_skipped += 1
                        continue
                    for qid in tag_qids:
                        name = resolve_tag_name(qid, qid_labels)
                        cur.execute(UPSERT_TAG_SQL, (name, qid))
                        tag_id = cur.fetchone()[0]
                        cur.execute(LINK_TAG_SQL, (composer_id, tag_id))
                        manual_added += 1

                cur.execute("SELECT id, wikidata_id FROM tags WHERE wikidata_id IS NOT NULL")
                tag_id_by_qid = {qid: tag_id for tag_id, qid in cur.fetchall()}
                wikilinks_inserted = 0
                tags_with_wikilinks = 0
                for qid, sitelinks in tag_sitelinks.items():
                    tag_id = tag_id_by_qid.get(qid)
                    if tag_id is None or not sitelinks:
                        continue
                    touched = False
                    for language, title in sitelinks.items():
                        cur.execute(INSERT_TAG_WIKILINK_SQL, (tag_id, language, title))
                        if cur.rowcount:
                            wikilinks_inserted += 1
                            touched = True
                    if touched:
                        tags_with_wikilinks += 1
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one tag"
          + (f", skipped {stale} stale cache entries" if stale else "") + "."
          + f" Applied {manual_added} MANUAL_COMPOSER_TAGS overrides"
          + (f" ({manual_skipped} composer(s) not found, skipped)" if manual_skipped else "") + "."
          + f" Loaded {wikilinks_inserted} tag_wikilinks for {tags_with_wikilinks} tags.")


if __name__ == "__main__":
    load()
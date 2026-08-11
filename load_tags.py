"""Load tags/composer_tags from the "movement" (P135) attribute already
fetched into wikidata_relationships.json by fetch_wikidata_relationships.py.
See schema.sql's comment on the tags table for why this repo calls
Wikidata's "movement" property "tags" instead.

Unlike load_instruments.py, wikidata_id (not name) is the upsert key here --
two distinct Wikidata items can share the identical English label (e.g.
Q2426218 and Q878985 both label as plain "modernism"), so name alone would
silently merge unrelated tags together.

EXCLUDED_QIDS and QID_REDIRECTS are hand-maintained curation, found by
reviewing the full tag list by hand (same spirit as classify_hu_wiki_
composers.py's category-keyword review, just for tags instead of pop-vs-
concert-music). See the entries below for why each one was added.
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

# Hand-maintained renames for tags whose plain Wikidata label collides with
# a different QID's label -- same pattern as this repo's other hand
# override lists (ERA_OVERRIDES, MANUAL_PLACE_CLUSTERS). Add an entry here
# once a collision like this is found; see schema.sql's tags comment.
NAME_OVERRIDES = {
    "Q2426218": "musical modernism",  # vs Q878985 "modernism" (the general movement)
}

# QIDs that turned up as P135 "movement" values but aren't real, usable
# movement concepts -- dropped entirely rather than loaded as a tag.
EXCLUDED_QIDS = {
    "Q28820001",  # "musical scene" -- Wikidata's own description is a generic
                  # placeholder ("a musical culture within a well-defined
                  # region and/or time-period"), not an actual named movement.
    "Q3328677",   # "Partitions de musique festive de danses de Paris au
                  # XIXème siècle" -- has no Wikidata description and no P31
                  # (instance of) claim at all; looks like a mis-scraped
                  # sheet-music collection/publication title, not a movement.
}

# QID -> QID: silently redirect a mistagged movement value to the one it
# almost certainly should have been. Q14378 "Neoclassicism" is the general
# 18th-century Greek/Roman-revival art movement (architecture, painting) --
# unrelated to music, and confirmed via Wikidata's own P31 typing (Q14378
# has no "musical movement" instance-of, only "art movement"). The only
# composer who ever carried it (Alfred Reed, a 20th-century American band
# composer) almost certainly should carry Q535611 "neoclassicism" instead --
# explicitly typed by Wikidata as a "twentieth-century movement in music",
# and the two are easy to confuse since musical Neoclassicism took its very
# name from the earlier art-historical movement as a deliberate allusion.
QID_REDIRECTS = {
    "Q14378": "Q535611",
}

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


def load():
    """Fully rebuilds tags/composer_tags from wikidata_relationships.json.
    Not incremental -- truncates first, so reruns after a fresh fetch don't
    leave stale links for composers whose recorded tags changed upstream."""
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    qid_labels = data.get("qid_labels", {})

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
                        # A composer merged/deleted (e.g. by
                        # merge_composers.py) since this cache entry was
                        # written -- the cache itself isn't updated by a
                        # merge, so a stale numeric key can outlive the
                        # composers row it once pointed to.
                        stale += 1
                        continue
                    tag_qids = entry.get("attributes", {}).get("movement", [])
                    if not tag_qids:
                        continue
                    processed += 1
                    for qid in tag_qids:
                        qid = QID_REDIRECTS.get(qid, qid)
                        if qid in EXCLUDED_QIDS:
                            continue
                        name = NAME_OVERRIDES.get(qid, qid_labels.get(qid, qid))
                        cur.execute(UPSERT_TAG_SQL, (name, qid))
                        tag_id = cur.fetchone()[0]
                        cur.execute(LINK_TAG_SQL, (int(composer_id), tag_id))
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one tag"
          + (f", skipped {stale} stale cache entries" if stale else "") + ".")


if __name__ == "__main__":
    load()
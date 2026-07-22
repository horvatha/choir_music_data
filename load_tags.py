"""Load tags/composer_tags from the "movement" (P135) attribute already
fetched into wikidata_relationships.json by fetch_wikidata_relationships.py.
See schema.sql's comment on the tags table for why this repo calls
Wikidata's "movement" property "tags" instead.

Unlike load_instruments.py, wikidata_id (not name) is the upsert key here --
two distinct Wikidata items can share the identical English label (e.g.
Q2426218 and Q878985 both label as plain "modernism"), so name alone would
silently merge unrelated tags together.
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
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_tags, tags RESTART IDENTITY CASCADE")
                for composer_id, entry in data["composers"].items():
                    if not entry.get("applied_to_db"):
                        continue
                    tag_qids = entry.get("attributes", {}).get("movement", [])
                    if not tag_qids:
                        continue
                    processed += 1
                    for qid in tag_qids:
                        name = NAME_OVERRIDES.get(qid, qid_labels.get(qid, qid))
                        cur.execute(UPSERT_TAG_SQL, (name, qid))
                        tag_id = cur.fetchone()[0]
                        cur.execute(LINK_TAG_SQL, (int(composer_id), tag_id))
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one tag.")


if __name__ == "__main__":
    load()
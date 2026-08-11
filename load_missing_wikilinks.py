"""Backfill composer_wikilinks from the "sitelinks" already cached in
wikidata_relationships.json for every composer that's in the DB -- not
just newly-loaded ones. A composer can have sitelinks fetched (e.g. by an
earlier fetch_wikidata_relationships.py run, or as a side effect of being
looked up as someone else's relation) without composer_wikilinks ever
having been populated for them, since no loader in this pipeline writes
that table from the general sitelinks cache -- only load_composers.py
(from the original era CSVs' own `article` column) and
load_missing_composers.py (which doesn't load wikilinks at all, just
name/alt-names) touch it.

When a composer has more than 10 sitelinks, only TARGET_LANGUAGES editions
are loaded (a very famous composer can have 100+ language editions; we
only care about the planned languages plus, implicitly, "en" since it's
always in TARGET_LANGUAGES). 10 or fewer is loaded as-is, language filter
or not, since that's cheap and there's no reason to throw away a rare
edition just because it isn't one of the 12 target languages.

Skips composers with no wikidata_id (nothing to look up) and composers
with no cached entry at all (never fetched by this pipeline).

Usage:
    python3 load_missing_wikilinks.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

INSERT_WIKILINK_SQL = """
    INSERT INTO composer_wikilinks (composer_id, language, title)
    VALUES (%s, %s, %s)
    ON CONFLICT DO NOTHING
"""


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["composers"]

    conn = psycopg2.connect()
    inserted = 0
    composers_touched = 0
    stale = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT composer_id, language FROM composer_wikilinks")
                existing = set(cur.fetchall())
                cur.execute("SELECT id FROM composers")
                real_composer_ids = {r[0] for r in cur.fetchall()}

                for key, entry in entries.items():
                    if not key.isdigit() or not entry.get("applied_to_db"):
                        continue
                    if int(key) not in real_composer_ids:
                        # Stale cache id -- see README.md's "Pipeline
                        # rules" (stale cache ids after a merge).
                        stale += 1
                        continue
                    sitelinks = entry.get("sitelinks", {})
                    if not sitelinks:
                        continue

                    composer_id = int(key)
                    items = sitelinks.items()
                    if len(items) > 10:
                        items = [(lang, title) for lang, title in items if lang in TARGET_LANGUAGES]

                    touched = False
                    for language, title in items:
                        if (composer_id, language) in existing:
                            continue
                        cur.execute(INSERT_WIKILINK_SQL, (composer_id, language, title))
                        if cur.rowcount:
                            inserted += 1
                            touched = True
                    if touched:
                        composers_touched += 1
    finally:
        conn.close()

    print(f"Inserted {inserted} wikilinks for {composers_touched} composers"
          + (f", skipped {stale} stale cache entries" if stale else "") + ".")


if __name__ == "__main__":
    main()

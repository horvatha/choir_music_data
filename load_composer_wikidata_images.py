"""Loads composer_wikidata_images from wikidata_relationships.json's
"images" field (see fetch_wikidata_relationships.py::extract_image()) --
URLs only, no downloaded bytes. Idempotent: TRUNCATEs and reinserts every
run, matching this repo's other from-cache loaders (e.g.
load_composer_alt_names.py) -- safe to rerun anytime the cache changes,
since the cache (not this table) is the source of truth for this data.

Usage:
    python3 load_composer_wikidata_images.py
"""
import psycopg2
import psycopg2.extras

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

INSERT_SQL = """
    INSERT INTO composer_wikidata_images (composer_id, full_url, thumb_url, is_preferred)
    VALUES %s
"""


def main():
    cache = load_cache(OUTPUT_FILE)
    composers = cache["composers"]

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM composers")
            existing_ids = {r[0] for r in cur.fetchall()}

        rows = []
        skipped_no_db_id = 0
        skipped_stale_id = 0
        for key, entry in composers.items():
            images = entry.get("images")
            if not images:
                continue
            if key.startswith("new:"):
                # "new:"-keyed entries are relation-discovery candidates not
                # yet loaded into the composers table at all -- no composer_id
                # to attach an image to yet (same convention as every other
                # from-cache loader here).
                skipped_no_db_id += 1
                continue
            composer_id = int(key)
            if composer_id not in existing_ids:
                # The cache can drift from the live DB (e.g. merge_composers.py
                # folding this id into another one since it was cached) --
                # skip rather than let a stale id break the whole load.
                skipped_stale_id += 1
                continue
            for img in images:
                rows.append((composer_id, img["url"], img["thumb_url"], img["is_preferred"]))

        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_wikidata_images RESTART IDENTITY")
                if rows:
                    psycopg2.extras.execute_values(cur, INSERT_SQL, rows)
    finally:
        conn.close()

    composers_with_images = len({r[0] for r in rows})
    preferred_count = sum(1 for r in rows if r[3])
    print(f"Loaded {len(rows)} images for {composers_with_images} composers "
          f"({preferred_count} marked preferred, {skipped_no_db_id} not-yet-loaded candidates skipped, "
          f"{skipped_stale_id} stale ids skipped).")


if __name__ == "__main__":
    main()

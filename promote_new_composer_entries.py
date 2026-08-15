"""Re-key wikidata_relationships.json's "new:<qid>" composer entries to
their real composer_id once they've actually been loaded into the
composers table (see load_missing_composers.py), and mark them
applied_to_db -- the same flag every other loader (load_composer_relations
.py, load_instruments.py, load_tags.py, load_works.py, ...) already checks
before processing an entry, since a "new:" entry's key isn't a real
composer_id yet.

Generic, not scoped to any one source CSV -- works for any "new:<qid>"
entry whose QID now matches an existing composers.wikidata_id, regardless
of which fetch script originally cached it.

Usage:
    python3 promote_new_composer_entries.py
"""

import psycopg2

from adapters.json_cache import load_cache, save_cache
from fetch_wikidata_relationships import OUTPUT_FILE


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data["composers"]

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT wikidata_id, id FROM composers WHERE wikidata_id IS NOT NULL")
            composer_id_by_qid = dict(cur.fetchall())
    finally:
        conn.close()

    promoted = 0
    for key in list(entries.keys()):
        if not key.startswith("new:"):
            continue
        qid = entries[key].get("qid")
        composer_id = composer_id_by_qid.get(qid)
        if composer_id is None:
            continue
        entry = entries.pop(key)
        entry["applied_to_db"] = True
        entries[str(composer_id)] = entry
        promoted += 1

    save_cache(OUTPUT_FILE, data)
    print(f"Promoted {promoted} \"new:\" entries to their real composer_id.")


if __name__ == "__main__":
    main()

"""Load composers.gender from the "gender" attribute (Wikidata P21)
already fetched into wikidata_relationships.json by
fetch_wikidata_relationships.py's extract_attributes().

GENDER_QID_MAP only covers the two values the gender column's enum
currently supports (see schema.sql) -- a composer whose gender QID(s)
don't map to exactly one of these (unrecognized QID, or more than one
recognized QID at once, which shouldn't happen for a real single-valued
field but is handled safely rather than guessed at) is left alone/skipped
rather than forced into one bucket. Reported on stdout so a genuine gap
(like Angela Morley's "trans woman" QID, Q1052281 -- see chat, composer
removed from the DB as a scope mismatch, unrelated to this) doesn't pass
silently.

Wikidata is the only source for this data, so it always sets gender
straight from the cache rather than COALESCE-preserving whatever was
there before -- same reasoning as birth_calendar/death_calendar in
load_birth_death_places.py -- safe to rerun after a fresh fetch.

Usage:
    python3 load_gender.py
"""
import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

GENDER_QID_MAP = {
    "Q6581097": "male",
    "Q6581072": "female",
}

UPDATE_GENDER_SQL = "UPDATE composers SET gender = %s WHERE id = %s"


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data["composers"]

    updated = 0
    unmapped = []
    conn = psycopg2.connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        for key, entry in entries.items():
            if key.startswith("new:"):
                continue
            gender_qids = entry.get("attributes", {}).get("gender", [])
            if not gender_qids:
                continue
            mapped = {GENDER_QID_MAP[q] for q in gender_qids if q in GENDER_QID_MAP}
            if len(mapped) != 1:
                unmapped.append((key, entry.get("name", ""), gender_qids))
                continue
            cur.execute(UPDATE_GENDER_SQL, (next(iter(mapped)), int(key)))
            updated += cur.rowcount

    print(f"{updated} composers' gender set.")
    if unmapped:
        print(f"{len(unmapped)} skipped (no single recognized gender QID):")
        for key, name, qids in unmapped:
            print(f"  {key} {name}: {qids}")


if __name__ == "__main__":
    main()

"""Regenerates composers.approximate_birth_year from scratch for every
composer -- a single sortable year derived only from birth_year/
birth_year_upper/birth_raw via domain/dates.py's estimate_year() (the
midpoint of a range, or the year itself for a point value; free-text
parsed from birth_raw only when birth_year itself is NULL). Never
touches flourish_start/flourish_end or death_year -- those aren't birth
data, so a composer with only one of those stays NULL here rather than
getting a guessed value from an unrelated proxy.

Idempotent and safe to rerun anytime (e.g. after a birth_year/birth_raw
change) -- always recomputed for every row, never incrementally patched,
so there's no risk of drifting out of sync with birth_year/birth_raw the
way composers.nationality has (see this repo's CLAUDE.md). The one
exception: review_missing_birth_years.py hand-sets this column directly
for composers with no birth_year/birth_raw at all, and that manually-set
value has no birth_year/birth_raw to be recomputed from -- rerunning
this script leaves such rows untouched (estimate_year() returns None for
them, and NULL-returning rows are simply skipped rather than
overwritten).

Usage:
    python3 backfill_approximate_birth_year.py
"""
import psycopg2

from domain.dates import estimate_year

SELECT_SQL = "SELECT id, birth_year, birth_year_upper, birth_raw FROM composers"
UPDATE_SQL = "UPDATE composers SET approximate_birth_year = %s WHERE id = %s"


def load():
    conn = psycopg2.connect()
    updated = 0
    still_null = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SELECT_SQL)
                rows = cur.fetchall()
                for composer_id, birth_year, birth_year_upper, birth_raw in rows:
                    year = estimate_year(birth_year, birth_year_upper, birth_raw)
                    if year is None:
                        still_null += 1
                        continue
                    cur.execute(UPDATE_SQL, (year, composer_id))
                    updated += 1
    finally:
        conn.close()
    print(f"approximate_birth_year: set for {updated} composers ({still_null} still NULL, nothing to derive it from).")


if __name__ == "__main__":
    load()

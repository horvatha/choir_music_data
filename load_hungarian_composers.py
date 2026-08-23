"""Merge composers_Hungarian.csv into the composers DB, skipping rows
flagged 'pop' by classify_hu_wiki_composers.py.

A Hungarian entry is matched onto an existing composer when there is
exactly one composer sharing its birth year (and death year, when both
sides know it) whose name -- unaccented, lowercased, split into words --
is the *same set of words*. Hungarian surname-first order doesn't matter
for a set comparison, so "Ligeti György" matches the existing "György
Ligeti" row. Matches get a composer_wikilinks(language='hu') row; rows
with no match are inserted as new composers.

This only catches same-alphabet reorderings. It will NOT catch a
genuinely translated name (Liszt Ferenc / Franz Liszt) or a differently
transliterated one (most Russian composers are spelled very differently
in Hungarian) -- those still get inserted as separate new composers here.
Run find_duplicate_composers.py afterwards to find same-birth/death-year
collisions worth merging by hand via composer_alt_names.
"""
import csv
import unicodedata

import psycopg2

from domain.dates import as_tuple, parse_free_text
from load_composers import (
    INSERT_COMPOSER_SQL,
    INSERT_WIKILINK_SQL,
    UPDATE_COMPOSER_SQL,
    UPSERT_ERA_SQL,
    LINK_ERA_SQL,
    clean,
)

SOURCE = "data/composers_Hungarian.csv"
LANGUAGE = "hu"

INSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""

FIND_CANDIDATES_BY_YEAR_SQL = """
    SELECT id, name, birth_year, death_year
    FROM composers
    WHERE birth_year = %(birth_year)s
      AND (%(death_year)s IS NULL OR death_year IS NULL OR death_year = %(death_year)s)
"""


def normalize_tokens(name):
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return frozenset(stripped.lower().split())


def rows_for_csv(path):
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("flag") == "pop":
                continue
            birth_year, birth_year_upper, birth_precision = as_tuple(parse_free_text(row.get("birth")))
            death_year, death_year_upper, death_precision = as_tuple(parse_free_text(row.get("death")))
            yield {
                "wiki_title": clean(row.get("article")),
                "name": clean(row.get("name")),
                "nationality": clean(row.get("nationality")),
                "birth_raw": clean(row.get("birth")),
                "birth_year": birth_year,
                "birth_year_upper": birth_year_upper,
                "birth_precision": birth_precision,
                "death_raw": clean(row.get("death")),
                "death_year": death_year,
                "death_year_upper": death_year_upper,
                "death_precision": death_precision,
                "flourish_raw": None,
                "flourish_start": None,
                "flourish_end": None,
                "era": clean(row.get("era")),
            }


def find_match(cur, record):
    if record["birth_year"] is None:
        return None
    cur.execute(FIND_CANDIDATES_BY_YEAR_SQL, {
        "birth_year": record["birth_year"],
        "death_year": record["death_year"],
    })
    candidates = cur.fetchall()
    if not candidates:
        return None

    hu_tokens = normalize_tokens(record["name"])
    matches = [c for c in candidates if normalize_tokens(c[1]) == hu_tokens]
    if len(matches) == 1:
        return matches[0]
    return None


def main():
    conn = psycopg2.connect()
    matched = 0
    inserted = 0
    ambiguous = []
    try:
        with conn:
            with conn.cursor() as cur:
                for record in rows_for_csv(SOURCE):
                    era = record.pop("era")
                    wiki_title = record.pop("wiki_title")
                    existing = find_match(cur, record)

                    if existing:
                        composer_id = existing[0]
                        cur.execute(UPDATE_COMPOSER_SQL, dict(record, id=composer_id))
                        # record["name"] is Hungarian surname-first order
                        # ("Ligeti György"); the matched composer's own name
                        # is whatever order the source that created it used
                        # ("György Ligeti") -- worth keeping both.
                        if record["name"] != existing[1]:
                            cur.execute(INSERT_ALT_NAME_SQL, (composer_id, LANGUAGE, record["name"]))
                        matched += 1
                    else:
                        cur.execute(INSERT_COMPOSER_SQL, record)
                        composer_id = cur.fetchone()[0]
                        inserted += 1

                    if wiki_title:
                        cur.execute(INSERT_WIKILINK_SQL, (composer_id, LANGUAGE, wiki_title))

                    if not existing and era:
                        cur.execute(UPSERT_ERA_SQL, (era,))
                        era_id = cur.fetchone()[0]
                        cur.execute(LINK_ERA_SQL, (composer_id, era_id))
    finally:
        conn.close()

    print(f"Matched onto an existing composer: {matched}")
    print(f"Inserted as a new composer: {inserted}")


if __name__ == "__main__":
    main()
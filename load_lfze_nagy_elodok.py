"""Load the 56 confirmed composers from composers_lfze_nagy_elodok.csv /
relations.json into other_webpages, linking each to its existing row in
the composers table.

Matching is by normalized name -- accents stripped, case-folded, split
into a token set so word order doesn't matter, since the LFZE source uses
Hungarian surname-first order ("Bartók Béla") while a composer loaded from
an English-language Wikipedia list may be stored the other way round
("Béla Bartók"). No new composer rows are created here: this source gives
no nationality or era, so a composer with zero or more-than-one same-name
candidate in the DB needs a human decision, not a guess -- those are
printed at the end instead of being loaded. When the LFZE name differs
from the matched composer's own name, it's recorded as a 'hu' alt name.

fetched_at is the saved markdown file's mtime (when the page was actually
crawled), not the time this loader happens to run.

Safe to rerun: other_webpages is upserted on its (composer_id, source)
primary key.

Usage:
    python3 load_lfze_nagy_elodok.py
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from adapters.name_matching import disambiguate_by_year, normalize_tokens

CSV_PATH = "composers_lfze_nagy_elodok.csv"
RELATIONS_PATH = "relations.json"
LFZE_DIR = Path(__file__).resolve().parent / "data" / "lfze"
SOURCE = "lfze_nagy_elodok"

FETCH_ALL_COMPOSERS_SQL = "SELECT id, name, birth_year, death_year FROM composers"

INSERT_OTHER_WEBPAGE_SQL = """
    INSERT INTO other_webpages (composer_id, source, url, language, title, author, fetched_at)
    VALUES (%(composer_id)s, %(source)s, %(url)s, %(language)s, %(title)s, %(author)s, %(fetched_at)s)
    ON CONFLICT (composer_id, source) DO UPDATE SET
        url = EXCLUDED.url, language = EXCLUDED.language, title = EXCLUDED.title,
        author = EXCLUDED.author, fetched_at = EXCLUDED.fetched_at
"""

INSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""



def load_rows():
    with open(RELATIONS_PATH, encoding="utf-8") as f:
        relations = json.load(f)["composers"]
    by_url = {entry["url"]: (slug, entry) for slug, entry in relations.items()}

    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            slug, entry = by_url[row["link"]]
            birth_year = int(entry["birth"]["date"][:4]) if entry.get("birth") else None
            death_year = int(entry["death"]["date"][:4]) if entry.get("death") else None
            md_path = LFZE_DIR / f"{slug}.md"
            fetched_at = datetime.fromtimestamp(md_path.stat().st_mtime, tz=timezone.utc)
            rows.append({
                "name": row["name"], "url": row["link"], "language": row["language"],
                "author": row["author"] or None, "birth_year": birth_year,
                "death_year": death_year, "fetched_at": fetched_at,
            })
    return rows


def main():
    rows = load_rows()

    conn = psycopg2.connect()
    conn.autocommit = True
    matched = []
    ambiguous = []
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_ALL_COMPOSERS_SQL)
            by_tokens = {}
            for cid, name, birth_year, death_year in cur.fetchall():
                by_tokens.setdefault(normalize_tokens(name), []).append((cid, name, birth_year, death_year))

            for row in rows:
                candidates = by_tokens.get(normalize_tokens(row["name"]), [])

                if len(candidates) != 1:
                    ambiguous.append((row["name"], candidates))
                    continue

                narrowed = disambiguate_by_year(candidates, row["birth_year"], lambda c: c[2])
                narrowed = disambiguate_by_year(narrowed, row["death_year"], lambda c: c[3])
                if len(narrowed) != 1:
                    ambiguous.append((row["name"], candidates))
                    continue

                cid, db_name, db_birth, db_death = narrowed[0]

                cur.execute(INSERT_OTHER_WEBPAGE_SQL, {
                    "composer_id": cid, "source": SOURCE, "url": row["url"],
                    "language": row["language"], "title": row["name"],
                    "author": row["author"], "fetched_at": row["fetched_at"],
                })
                if row["name"] != db_name:
                    cur.execute(INSERT_ALT_NAME_SQL, (cid, "hu", row["name"]))
                matched.append((row["name"], db_name, cid))
    finally:
        conn.close()

    print(f"Linked {len(matched)} composers to other_webpages:")
    for lfze_name, db_name, cid in matched:
        note = "" if lfze_name == db_name else f"  (DB name: {db_name!r})"
        print(f"  {lfze_name} -> composer_id={cid}{note}")

    if ambiguous:
        print(f"\nNot loaded -- no single matching composer ({len(ambiguous)}):")
        for name, candidates in ambiguous:
            if not candidates:
                print(f"  {name}: no match in DB")
            else:
                ids = ", ".join(f"id={c[0]} ({c[1]}, b.{c[2]} d.{c[3]})" for c in candidates)
                print(f"  {name}: {ids}")


if __name__ == "__main__":
    main()

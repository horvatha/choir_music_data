"""Cross-references composers_polmic.csv (is_composer=true rows only --
POLMIC's index mixes composers with musicologists/performers/institutions,
see fetch_polmic.py) against this repo's own composers table, writing a
copy of the CSV with two extra columns:

    in_the_db     -- "true"/"false"
    wikidata_id   -- that composer's wikidata_id if found and unambiguous,
                      else blank (never guessed)

Same matching approach as match_swedish_heritage_composers.py -- normalized
name (accents stripped, case-folded, token set so word order doesn't
matter) via adapters/name_matching's normalize_tokens(), disambiguated by
birth year (adapters/name_matching's disambiguate_by_year()) when more
than one DB composer shares the same normalized name. A composer whose
POLMIC name doesn't token-match any DB name exactly is reported as not in
the DB even if they may actually be there under a different spelling --
this is a read-only cross-reference for a human to review, not a merge,
so a false "not in the DB" costs nothing but a look.

Reads the input CSV, never touches it -- writes a separate output file.

Usage:
    python3 match_polmic_composers.py
    python3 match_polmic_composers.py --in path/to/in.csv --out path/to/out.csv
"""
import csv
import re
import sys
from pathlib import Path

import click
import psycopg2

from adapters.name_matching import disambiguate_by_year, normalize_tokens

DEFAULT_IN_PATH = Path(__file__).resolve().parent / "data" / "POLMIC" / "composers_polmic.csv"
DEFAULT_OUT_PATH = Path(__file__).resolve().parent / "data" / "POLMIC" / "composers_polmic_matched.csv"

YEAR_RE = re.compile(r"\d{4}")


def _extract_year(date_str: str) -> int | None:
    m = YEAR_RE.search(date_str or "")
    return int(m.group(0)) if m else None


def load_composer_index() -> dict:
    """normalized name tokens -> list of (id, wikidata_id, birth_year)."""
    conn = psycopg2.connect()
    index: dict[frozenset, list] = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, wikidata_id, birth_year FROM composers")
            for composer_id, name, wikidata_id, birth_year in cur.fetchall():
                if not name:
                    continue
                key = normalize_tokens(name)
                if not key:
                    continue
                index.setdefault(key, []).append((composer_id, wikidata_id, birth_year))
    finally:
        conn.close()
    return index


def match_row(row: dict, index: dict) -> tuple[bool, str]:
    key = normalize_tokens(row["name"])
    candidates = index.get(key, [])
    if not candidates:
        return False, ""
    if len(candidates) == 1:
        _id, wikidata_id, _birth_year = candidates[0]
        return True, wikidata_id or ""

    row_year = _extract_year(row.get("birth_date", ""))
    year_matches = disambiguate_by_year(candidates, row_year, lambda c: c[2])
    if len(year_matches) == 1:
        _id, wikidata_id, _birth_year = year_matches[0]
        return True, wikidata_id or ""

    print(f"  ambiguous: {row['name']!r} matches {len(candidates)} DB composers "
          f"(ids {[c[0] for c in candidates]}), not resolved -- wikidata_id left blank", file=sys.stderr)
    return True, ""


@click.command()
@click.option("--in", "in_path", type=click.Path(exists=True), default=str(DEFAULT_IN_PATH))
@click.option("--out", "out_path", type=click.Path(), default=str(DEFAULT_OUT_PATH))
def main(in_path: str, out_path: str):
    print("Loading composer index from the DB...")
    index = load_composer_index()
    print(f"{len(index)} distinct normalized names in the DB")

    with open(in_path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["is_composer"] == "true"]
    print(f"{len(rows)} POLMIC rows with is_composer=true")

    in_db = 0
    with_wikidata_id = 0
    for row in rows:
        matched, wikidata_id = match_row(row, index)
        row["in_the_db"] = "true" if matched else "false"
        row["wikidata_id"] = wikidata_id
        if matched:
            in_db += 1
        if wikidata_id:
            with_wikidata_id += 1

    fieldnames = list(rows[0].keys()) if rows else ["name", "is_composer", "birth_date", "birth_place", "death_date", "death_place", "url", "in_the_db", "wikidata_id"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} rows processed")
    print(f"in_the_db=true: {in_db} ({in_db - with_wikidata_id} of those with wikidata_id blank -- "
          f"either a genuinely ambiguous match (see stderr) or the matched DB composer simply has no "
          f"wikidata_id of its own yet)")
    print(f"in_the_db=false: {len(rows) - in_db}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

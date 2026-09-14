"""For the composers already matched to this repo's DB (in_the_db=true
in composers_swedish_heritage_matched.csv), compares Swedish Heritage's
parsed day-precision birth/death dates against what's currently in our
DB (birth_date/death_date, itself sourced from Wikidata via the normal
pipeline), to find candidates for a Wikidata fix -- per the "fix
Wikidata first, then fetch and use" workflow: this script only reports
candidates, it does not write anywhere.

Three buckets per date (birth, death), each checked independently:
  - "would add"  -- our DB has no day-precision date at all here, SH has one
  - "conflict"   -- our DB has a day-precision date that DISAGREES with SH
  - (agrees, or SH has nothing to contribute -- not reported)

Prints a report; writes nothing to the DB or to Wikidata. Read-only.

Usage:
    python3 compare_swedish_heritage_dates.py
"""
import csv
import re
from pathlib import Path

import psycopg2

MATCHED_CSV = Path(__file__).resolve().parent / "data" / "Swedish_Heritage" / "composers_swedish_heritage_matched.csv"

SV_MONTHS = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DATE_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\.?,?\s+([A-Za-zåäöÅÄÖ]+)\.?,?\s+(\d{4})")


def parse_date(raw: str):
    """"29 augusti 1881" / "3 May 1773" / "1st May, 1872" -> (year, month, day), or None."""
    if not raw:
        return None
    m = DATE_RE.search(raw)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = SV_MONTHS.get(month_name.lower()) or EN_MONTHS.get(month_name.lower())
    if not month:
        return None
    return int(year), month, int(day)


def main():
    with open(MATCHED_CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["in_the_db"] == "true" and r["wikidata_id"]]

    conn = psycopg2.connect()
    would_add_birth, conflict_birth = [], []
    would_add_death, conflict_death = [], []
    try:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    "SELECT id, birth_date, birth_year, death_date, death_year FROM composers WHERE wikidata_id = %s",
                    (row["wikidata_id"],),
                )
                db_row = cur.fetchone()
                if not db_row:
                    continue
                composer_id, db_birth_date, db_birth_year, db_death_date, db_death_year = db_row

                sh_birth = parse_date(row["birth_date"])
                if sh_birth:
                    if db_birth_date is None:
                        would_add_birth.append((composer_id, row["name"], row["wikidata_id"], sh_birth, row["url"]))
                    else:
                        db_tuple = (db_birth_date.year, db_birth_date.month, db_birth_date.day)
                        if db_tuple != sh_birth:
                            conflict_birth.append((composer_id, row["name"], row["wikidata_id"], db_tuple, sh_birth, row["url"]))

                sh_death = parse_date(row["death_date"])
                if sh_death:
                    if db_death_date is None:
                        would_add_death.append((composer_id, row["name"], row["wikidata_id"], sh_death, row["url"]))
                    else:
                        db_tuple = (db_death_date.year, db_death_date.month, db_death_date.day)
                        if db_tuple != sh_death:
                            conflict_death.append((composer_id, row["name"], row["wikidata_id"], db_tuple, sh_death, row["url"]))
    finally:
        conn.close()

    print(f"{len(rows)} matched composers checked\n")

    print(f"=== BIRTH: would add day-precision date ({len(would_add_birth)}) ===")
    for composer_id, name, wikidata_id, sh_date, url in would_add_birth:
        print(f"  [{composer_id}] {name} ({wikidata_id}): SH says {sh_date[0]:04d}-{sh_date[1]:02d}-{sh_date[2]:02d}  {url}")

    print(f"\n=== BIRTH: conflicts with existing DB date ({len(conflict_birth)}) ===")
    for composer_id, name, wikidata_id, db_date, sh_date, url in conflict_birth:
        print(f"  [{composer_id}] {name} ({wikidata_id}): DB has {db_date[0]:04d}-{db_date[1]:02d}-{db_date[2]:02d}, "
              f"SH says {sh_date[0]:04d}-{sh_date[1]:02d}-{sh_date[2]:02d}  {url}")

    print(f"\n=== DEATH: would add day-precision date ({len(would_add_death)}) ===")
    for composer_id, name, wikidata_id, sh_date, url in would_add_death:
        print(f"  [{composer_id}] {name} ({wikidata_id}): SH says {sh_date[0]:04d}-{sh_date[1]:02d}-{sh_date[2]:02d}  {url}")

    print(f"\n=== DEATH: conflicts with existing DB date ({len(conflict_death)}) ===")
    for composer_id, name, wikidata_id, db_date, sh_date, url in conflict_death:
        print(f"  [{composer_id}] {name} ({wikidata_id}): DB has {db_date[0]:04d}-{db_date[1]:02d}-{db_date[2]:02d}, "
              f"SH says {sh_date[0]:04d}-{sh_date[1]:02d}-{sh_date[2]:02d}  {url}")


if __name__ == "__main__":
    main()

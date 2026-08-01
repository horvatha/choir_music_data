"""Load works.composed_*/premiered_*/published_* from the "inception"
(P571), "first_performance" (P1191), and "publication_date" (P577) fields
of the "work_attributes" cache fetch_work_details.py wrote into
wikidata_relationships.json.

Only loads from year-level precision up (Wikidata precision 9/10/11) --
century/decade-precision claims (precision 7/8, e.g. "9th century") are
skipped entirely rather than mapped onto an arbitrary year; the *_year
column stays NULL for those rather than encoding a guess.

A work can in principle carry more than one statement for a given field
(rare, none seen in this dataset for inception/publication_date, but
Wikidata doesn't declare any of these three single-value); the first
year-or-finer one found is used.

Usage:
    python3 load_work_dates.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

# (work_attributes field, year column, month column, day column)
DATE_FIELDS = [
    ("inception", "composed_year", "composed_month", "composed_day"),
    ("first_performance", "premiered_year", "premiered_month", "premiered_day"),
    ("publication_date", "published_year", "published_month", "published_day"),
]

UPDATE_WORK_DATES_SQL = """
    UPDATE works SET
        composed_year = %s, composed_month = %s, composed_day = %s,
        premiered_year = %s, premiered_month = %s, premiered_day = %s,
        published_year = %s, published_month = %s, published_day = %s
    WHERE id = %s
"""


def parse_time(value):
    """Wikidata time value -> (year, month, day), month/day None below
    that field's precision. value["time"] looks like
    "+1892-04-28T00:00:00Z" -- sign, then zero-padded year, month, day."""
    sign = -1 if value["time"].startswith("-") else 1
    year_str, month_str, day_str = value["time"][1:].split("-", 2)
    precision = value["precision"]
    year = sign * int(year_str)
    month = int(month_str) if precision >= 10 else None
    day = int(day_str[:2]) if precision >= 11 else None
    return year, month, day


def extract_date(attrs, field):
    values = attrs.get(field)
    if not values:
        return None, None, None
    value = values[0]
    if value["precision"] < 9:
        return None, None, None
    return parse_time(value)


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})

    conn = psycopg2.connect()
    loaded = {field: 0 for field, *_ in DATE_FIELDS}
    skipped_low_precision = {field: 0 for field, *_ in DATE_FIELDS}
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL")
                for work_id, wikidata_id in cur.fetchall():
                    attrs = work_attributes.get(wikidata_id)
                    if not attrs:
                        continue
                    dates = []
                    for field, *_ in DATE_FIELDS:
                        year, month, day = extract_date(attrs, field)
                        if field in attrs:
                            if year is None:
                                skipped_low_precision[field] += 1
                            else:
                                loaded[field] += 1
                        dates.extend([year, month, day])
                    if any(d is not None for d in dates):
                        cur.execute(UPDATE_WORK_DATES_SQL, (*dates, work_id))
    finally:
        conn.close()
    for field, *_ in DATE_FIELDS:
        print(f"{field}: loaded {loaded[field]} works ({skipped_low_precision[field]} skipped, below year precision).")


if __name__ == "__main__":
    load()

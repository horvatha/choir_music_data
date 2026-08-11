"""Approximate a composer's birth year from the DB's birth_year/
birth_year_upper/birth_raw columns (schema.sql), as plain functions over
ints/strings -- callers pass the column values in, nothing here touches
the DB.
"""
import re

CENTURY_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)\s+century", re.IGNORECASE)


def approximate_birth_year(year, year_end=None):
    if year is None:
        return None
    if year_end is None:
        return year
    return (year + year_end) // 2


def century_to_year_range(text):
    """Parse an 'Nth century' phrase into (year, year_end), e.g.
    '10th century' -> (900, 1000). A 'late'/'later'/'second half of the'
    qualifier narrows it to the second half (e.g. 'late 15th century' ->
    (1450, 1500)); 'early'/'first half of the' narrows it to the first
    half (e.g. 'early 16th century' -> (1500, 1550)). No qualifier keeps
    the full century span."""
    if text is None:
        return None, None
    match = CENTURY_RE.search(text)
    if not match:
        return None, None
    century = int(match.group(1))
    start, end = (century - 1) * 100, century * 100
    lower = text.lower()
    if "second half" in lower or "late" in lower:
        return start + 50, end
    if "first half" in lower or "early" in lower:
        return start, start + 50
    return start, end


def estimate_birth_year(year, year_end, raw):
    """Estimate a composer's birth year from the DB's birth_year/
    birth_year_upper/birth_raw columns together: birth_year/birth_year_upper
    win whenever birth_year is set (birth_raw is ignored then, matching
    load_composers.py's parse_date() -- birth_raw is the original text
    whether or not it was parseable, birth_year is only set once something
    concrete was extracted from it, from that same text or a later
    Wikidata backfill); only when birth_year is NULL is birth_raw parsed
    as a century phrase as a fallback."""
    if year is None:
        year, year_end = century_to_year_range(raw)
    return approximate_birth_year(year, year_end)

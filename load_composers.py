"""Load composer CSVs (one per era) into Postgres.

Composers are keyed by their English Wikipedia page (recorded in
composer_wikilinks with language='en'): a composer appearing in multiple
era CSVs is merged into one `composers` row, with the earliest-loaded
non-null values winning on conflict, and linked to every era it appears
in via `composer_eras`. Composers with no Wikipedia page fall back to an
exact name match among other wikilink-less composers. Safe to rerun.

Connection is taken from standard libpq environment variables
(PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD) so no credentials
live in this file. Run `psql -f schema.sql` once before the first load.
"""
import math
import re
from datetime import date

import pandas as pd
import psycopg2

from domain.dates import as_tuple, parse_free_text

# era -> csv file
SOURCES = {
    "Medieval": "data/eras/composers_Medieval.csv",
    "Renaissance": "data/eras/composers_Renaissance.csv",
    "Baroque": "data/eras/composers_Baroque.csv",
    "Classical-era": "data/eras/composers_Classical-era.csv",
    "Romantic-era": "data/eras/composers_Romantic-era.csv",
    "20th-century": "data/eras/composers_20th_century.csv",
    "21st-century": "data/eras/composers_21st_century.csv",
}

FLOURISH_DASH_RE = re.compile(r"\s*[–—]\s*")  # en dash / em dash
SHORT_YEAR_RE = re.compile(r"\b(\d{1,2})\b")
ANY_YEAR_RE = re.compile(r"(\d{3,4})")


def parse_flourish(raw):
    """Parse a flourish field like '1405?-after 1433' into (start, end).

    The source lists mostly separate a range with an en dash ('1120-47'),
    reserving the plain hyphen for a sub-range within one side ('1401-20 -
    after 1436'). Splitting on the plain hyphen first would break on the en
    dash side and silently drop the end year, so the en/em dash is tried
    first and the plain hyphen is only a fallback for ranges that don't use
    one. A short 1-2 digit end ('1120-47') is shorthand for the same
    century/decade as the start year (i.e. 1147), not a 2-digit year on its
    own, since 'ANY_YEAR_RE' requires 3-4 digits.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None
    text = str(raw).strip()
    if not text:
        return None, None

    if FLOURISH_DASH_RE.search(text):
        start_part, end_part = FLOURISH_DASH_RE.split(text, maxsplit=1)
    else:
        start_part, _, end_part = text.partition("-")

    start = ANY_YEAR_RE.search(start_part)
    start_year = int(start.group(1)) if start else None

    end = ANY_YEAR_RE.search(end_part) if end_part else None
    end_year = int(end.group(1)) if end else None

    if end_year is None and end_part and start_year is not None:
        short = SHORT_YEAR_RE.search(end_part)
        if short:
            digits = short.group(1)
            magnitude = 10 ** len(digits)
            end_year = (start_year // magnitude) * magnitude + int(digits)

    return start_year, end_year


def clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        # pandas reads numeric-looking columns with some blank cells as
        # float64, turning a clean "1957" into 1957.0.
        value = int(value)
    text = str(value).strip()
    return text or None


INSERT_COMPOSER_SQL = """
    INSERT INTO composers (
        name, nationality,
        birth_raw, birth_year, birth_year_upper, birth_precision,
        death_raw, death_year, death_year_upper, death_precision,
        flourish_raw, flourish_start, flourish_end
    ) VALUES (
        %(name)s, %(nationality)s,
        %(birth_raw)s, %(birth_year)s, %(birth_year_upper)s, %(birth_precision)s,
        %(death_raw)s, %(death_year)s, %(death_year_upper)s, %(death_precision)s,
        %(flourish_raw)s, %(flourish_start)s, %(flourish_end)s
    )
    RETURNING id
"""

UPDATE_COMPOSER_SQL = """
    UPDATE composers SET
        nationality      = COALESCE(nationality, %(nationality)s),
        birth_raw        = COALESCE(birth_raw, %(birth_raw)s),
        birth_year       = COALESCE(birth_year, %(birth_year)s),
        birth_year_upper = COALESCE(birth_year_upper, %(birth_year_upper)s),
        birth_precision  = COALESCE(birth_precision, %(birth_precision)s),
        death_raw        = COALESCE(death_raw, %(death_raw)s),
        death_year       = COALESCE(death_year, %(death_year)s),
        death_year_upper = COALESCE(death_year_upper, %(death_year_upper)s),
        death_precision  = COALESCE(death_precision, %(death_precision)s),
        flourish_raw     = COALESCE(flourish_raw, %(flourish_raw)s),
        flourish_start   = COALESCE(flourish_start, %(flourish_start)s),
        flourish_end     = COALESCE(flourish_end, %(flourish_end)s)
    WHERE id = %(id)s
"""

INSERT_WIKILINK_SQL = """
    INSERT INTO composer_wikilinks (composer_id, language, title)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""

UPSERT_ERA_SQL = """
    INSERT INTO eras (name) VALUES (%s)
    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

LINK_ERA_SQL = """
    INSERT INTO composer_eras (composer_id, era_id) VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""

# A composer is merged on a normalized form of their 'en' wikilink title,
# since some era CSVs store the plain display name in `article` instead of
# a real Wikipedia slug (e.g. "Jean Sibelius" vs "Jean_Sibelius"). Also
# collapses whitespace immediately after a period (regexp_replace #2) so a
# CSV's "E.T.A. Hoffmann" matches the stored wikilink's "E. T. A.
# Hoffmann" -- same normalization find_composer()'s own norm_key applies
# in Python, both sides must match (found 2026-08-23: this gap silently
# duplicated Hoffmann on every rerun since the two spellings never
# compared equal).
FIND_COMPOSER_BY_WIKILINK_SQL = r"""
    SELECT c.id, c.birth_year, c.death_year
    FROM composer_wikilinks w
    JOIN composers c ON c.id = w.composer_id
    WHERE w.language = %s
      AND lower(regexp_replace(regexp_replace(w.title, '_', ' ', 'g'), '\.\s+', '.', 'g')) = %s
"""

# Composers with no Wikipedia page have no natural merge key; fall back to
# an exact name match among other wikilink-less composers so reloading the
# same CSVs doesn't keep inserting fresh duplicates.
FIND_COMPOSER_BY_NAME_NO_WIKILINK_SQL = """
    SELECT c.id, c.birth_year, c.death_year
    FROM composers c
    WHERE c.name = %s
      AND NOT EXISTS (
          SELECT 1 FROM composer_wikilinks w WHERE w.composer_id = c.id
      )
"""

# Two different Wikipedia lists citing slightly different birth/death years
# for the same person is normal for a historical composer, but *not* for a
# modern one -- a centuries-old date is often only known from secondary
# scholarship that can genuinely disagree by several years (verified via
# Pomponio Nenna, composer id 562: en.wikipedia's current text gives
# "baptized 13 June 1556 - 25 July 1608", but one of this repo's own
# source CSVs has "c. 1550"-1613 for the same real person, a 5-6 year
# disagreement), whereas a 20th/21st-century composer's dates are
# ordinarily well documented and a multi-year discrepancy far more likely
# means two different real people who happen to share a name (see James
# Lavino: one born 1937, an entirely different one born 1973). Rather than
# a flat tolerance (too loose for modern composers if widened to cover
# Nenna, too tight for Nenna if kept modern-safe) or a hard cutoff between
# two flat values (an arbitrary cliff at whatever year is chosen),
# TOLERANCE_SCALE * sqrt(years before today) grows the tolerance smoothly
# the further back the composer lived -- matches this repo's existing
# "the further back the composer lived, treat sourcing with more
# skepticism" convention (see CLAUDE.md's nationality-vs-citizenship
# section, same reasoning applied to dates here).
#
# Calibrated (2026-08-23) against real cases, ceil()'d rather than
# round()'d deliberately -- a false "different person" here just creates
# a harmless duplicate row to clean up later; a false "same person" would
# silently overwrite one real person's data with another's, a much worse
# failure mode, so ties are broken toward the safer outcome. (ceil() also
# means the result is never 0 for any years_ago > 0, so no extra floor
# needs enforcing below -- floor() was tried first and gave a bigger
# safety margin on the Leclair case just below [4 vs. ceil's 5, against
# his real 6-year gap], but still resolves it correctly either way, and
# ceil() is the simpler expression.)
#   - Pomponio Nenna (composer 562, Q3907903): en.wikipedia gives
#     "baptized 13 June 1556 - 25 July 1608"; this repo's own CSV has
#     "c. 1550"-1613 for the same real person -- must resolve to "same".
#   - Jean-Marie Leclair l'aine vs. le cadet (composers 1551/1613,
#     Q348875/Q6169629 -- distinct QIDs, the second has its own "the
#     younger"/"le cadet" wikilinks, a documented nephew, not the same
#     person): 1697-1764 vs. 1703-1777, only a 6/13-year gap -- must
#     resolve to "different" despite the small gap, since an *initial*
#     naive fit (TOLERANCE_SCALE=0.35, round() instead of floor()) got
#     this wrong, verified only by separately checking this pair's own
#     Wikidata items directly, not by trusting the Nenna fit alone.
#   - Louis Aubert (composers 1741/9486... and separately 3018/9267):
#     an 1720-1800 composer and an entirely separate 1877-1968 one share
#     the name -- 80+ years apart, must resolve to "different" at any
#     plausible tolerance.
# All three re-verified against the whole DB's same-name composer pairs
# after picking TOLERANCE_SCALE=0.25, not just these three points.
TOLERANCE_SCALE = 0.25
MIN_YEAR_TOLERANCE = 1
LARGE_BIRTH_GAP = 15


def _year_diff(a, b):
    return None if a is None or b is None else abs(a - b)


def _year_tolerance(existing_birth, new_birth):
    # Whichever birth year is known (prefer the existing DB row's, since
    # it's already been through this same check once) is the reference
    # point; if neither is known, MIN_YEAR_TOLERANCE is the safe default
    # rather than guessing a historical-sized allowance.
    reference_year = existing_birth if existing_birth is not None else new_birth
    if reference_year is None:
        return MIN_YEAR_TOLERANCE
    years_ago = date.today().year - reference_year
    if years_ago <= 0:
        return MIN_YEAR_TOLERANCE
    return math.ceil(TOLERANCE_SCALE * math.sqrt(years_ago))


def looks_like_different_person(existing_birth, existing_death, new_birth, new_death):
    birth_diff = _year_diff(existing_birth, new_birth)
    death_diff = _year_diff(existing_death, new_death)
    tolerance = _year_tolerance(existing_birth, new_birth)
    if birth_diff is not None and death_diff is not None:
        return birth_diff > tolerance and death_diff > tolerance
    if birth_diff is not None:
        return birth_diff > LARGE_BIRTH_GAP
    return False


def rows_for_csv(path):
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        birth_year, birth_year_upper, birth_precision = as_tuple(parse_free_text(row.get("birth")))
        death_year, death_year_upper, death_precision = as_tuple(parse_free_text(row.get("death")))
        flourish_start, flourish_end = parse_flourish(row.get("flourish"))

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
            "flourish_raw": clean(row.get("flourish")),
            "flourish_start": flourish_start,
            "flourish_end": flourish_end,
        }


def main():
    conn = psycopg2.connect()  # reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD
    try:
        with conn:
            with conn.cursor() as cur:
                def find_composer(wiki_title, name):
                    if wiki_title is not None:
                        # Postgres's lower() does simple (non-Turkish-aware)
                        # case mapping: 'İ' (U+0130, dotted capital I) ->
                        # plain 'i'. Python's str.lower() instead follows
                        # Unicode's SpecialCasing rules and produces 'i' +
                        # a combining dot above (U+0307) -- a different
                        # string that doesn't match what's actually stored
                        # via the SQL-side lower(), causing find_composer to
                        # miss an existing row and attempt a duplicate
                        # insert (verified: İlhan Usmanbaş, present in both
                        # composers_20th_century.csv and
                        # composers_21st_century.csv). Replacing İ with
                        # plain I before lowering matches Postgres's simpler
                        # behavior.
                        norm_key = wiki_title.replace("_", " ").replace("İ", "I").lower()
                        norm_key = re.sub(r"\.\s+", ".", norm_key)
                        cur.execute(FIND_COMPOSER_BY_WIKILINK_SQL, ("en", norm_key))
                    else:
                        cur.execute(FIND_COMPOSER_BY_NAME_NO_WIKILINK_SQL, (name,))
                    return cur.fetchone()

                for era, path in SOURCES.items():
                    cur.execute(UPSERT_ERA_SQL, (era,))
                    era_id = cur.fetchone()[0]

                    count = 0
                    for record in rows_for_csv(path):
                        wiki_title = record.pop("wiki_title")
                        existing = find_composer(wiki_title, record["name"])

                        if existing and looks_like_different_person(
                            existing[1], existing[2],
                            record["birth_year"], record["death_year"],
                        ):
                            # Same normalized wikilink/name, but the dates say
                            # this is a different person who happens to share
                            # it; disambiguate instead of merging them. Look up
                            # the disambiguated title too, so a rerun matches
                            # the composer created on a previous run instead of
                            # inserting a duplicate.
                            if wiki_title is not None:
                                wiki_title = f"{wiki_title} ({era})"
                                existing = find_composer(wiki_title, record["name"])
                            else:
                                existing = None

                        if existing:
                            composer_id = existing[0]
                            cur.execute(UPDATE_COMPOSER_SQL, dict(record, id=composer_id))
                        else:
                            cur.execute(INSERT_COMPOSER_SQL, record)
                            composer_id = cur.fetchone()[0]

                        if wiki_title is not None:
                            cur.execute(INSERT_WIKILINK_SQL, (composer_id, "en", wiki_title))

                        cur.execute(LINK_ERA_SQL, (composer_id, era_id))
                        count += 1
                    print(f"{era}: processed {count} rows from {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
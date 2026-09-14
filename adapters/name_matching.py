"""Shared name-matching helpers for this repo's page-scraping "match
against our own composers table" scripts (load_lfze_nagy_elodok.py,
match_swedish_heritage_composers.py, load_swedish_heritage.py, ...) --
was three near-identical copies of normalize_tokens(), one per script.

Matching by normalized name (accents stripped, case-folded, split into a
token set so word order doesn't matter) handles a source using a
different name order/script than composers.name (e.g. LFZE's Hungarian
surname-first "Bartók Béla" vs. an English-list-loaded "Béla Bartók"),
but each caller's *disambiguation* when more than one DB composer shares
a normalized name differs enough (which year(s) to check, what
tolerance) that it's kept per-caller rather than forced into one
one-size-fits-all function here -- see disambiguate_by_year for the one
piece of that which several callers do share.
"""
import re
import unicodedata


def normalize_tokens(name: str) -> frozenset:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return frozenset(re.findall(r"[a-z]+", stripped.lower()))


def disambiguate_by_year(candidates, target_year, year_getter, tolerance=2):
    """Narrow a list of same-normalized-name candidates down using a
    year both sides should roughly agree on if they're really the same
    person -- e.g. birth year. target_year/candidate years of None are
    never treated as a mismatch (nothing to compare), matching this
    repo's existing convention (same tolerance load_composers.py's
    looks_like_different_person and load_lfze_nagy_elodok.py's
    year_mismatch use) that two sources disagreeing by a year or two is
    normal sourcing noise, not evidence of a different person.

    year_getter(candidate) -> int | None. Returns the filtered list
    (unchanged if target_year is None -- nothing to filter by)."""
    if target_year is None:
        return candidates
    return [
        c for c in candidates
        if year_getter(c) is None or abs(year_getter(c) - target_year) <= tolerance
    ]

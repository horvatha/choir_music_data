"""Shared day-precision date parsing for this repo's page-scraping
fetchers (fetch_swedish_heritage.py, fetch_polmic.py, ...) -- pulling a
composer's birth/death date out of free-text biography prose, English
only (site-specific languages, e.g. fetch_swedish_heritage.py's Swedish
patterns, stay local to that script -- not every source has one, and
forcing them in here wouldn't actually be reused yet).

DAY_PRECISION_DATE matches a "29 August 1881" / "1st May, 1872" /
"24th September 1914" shaped date (day, optional ordinal suffix, month
name, optional comma, year) -- deliberately just this one shape; each
site's own full sentence-pattern regexes (born in PLACE on DATE, etc.)
are still built per-script around it, since sentence structure varies
site to site even when the date token itself doesn't.

parse_abbreviated_birth_death() handles one specific, but apparently
common, shape across multiple unrelated sources: "b. DATE in/,) PLACE
... d. DATE in/,) PLACE" (found first on swedishmusicalheritage.com's
Bror Beckman/Erik Gustaf Geijer entries, then again verbatim on
polmic.pl's Andrzej Panufnik entry: "b. 24th September 1914 in Warsaw,
d. 27th October 1991 in Twickenham") -- worth sharing since it's
recurred exactly, not a coincidence of one site.
"""
import re

DAY_PRECISION_DATE = r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\.?,?\s+\d{4}"

_B_ABBREV_RE = re.compile(r"\bb\.\s+(%s)(?:\s+in\s+|,\s*)([^.,]+)" % DAY_PRECISION_DATE)
_D_ABBREV_RE = re.compile(r"\bd\.\s+(%s)(?:\s+in\s+|,\s*)([^.,]+)" % DAY_PRECISION_DATE)


def _empty():
    return {"place": None, "date": None, "raw": None}


def parse_abbreviated_birth_death(text: str) -> tuple[dict, dict]:
    """Returns (birth, death), each {"place", "date", "raw"} -- "raw" is
    the exact matched substring, for callers that want to show their
    work. Either half is the all-None _empty() dict if that pattern
    isn't found (e.g. only a death date given, or neither in this
    shape at all -- not every source uses "b."/"d.")."""
    birth = _empty()
    death = _empty()

    m = _B_ABBREV_RE.search(text)
    if m:
        birth = {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}

    m = _D_ABBREV_RE.search(text)
    if m:
        death = {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}

    return birth, death

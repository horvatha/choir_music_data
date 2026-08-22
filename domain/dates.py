"""Consolidates this repo's date-interpretation rules -- the judgment
calls about how to read an uncertain/conflicting date claim, as opposed
to the mechanics of fetching one (adapters/wikidata_api.py) or storing
one (the load_*.py scripts' SQL). Every function here is pure: plain
Python values in, plain Python values out -- no DB connection, no HTTP
call, no knowledge of Wikidata's JSON claim shape. Callers (fetch_
wikidata_relationships.py, load_composers.py, verify_exact_agreeing_
dates.py) do their own format-specific parsing (JSON claim / CSV text)
down to the plain shapes used here, then hand off the actual "what do we
believe" decision to this module.

This consolidates three previously-separate, already-inconsistent
implementations of "resolve an uncertain date" found during a single
session of hand-debugging real composers (Panchenko, Bertheaume, Odo of
Arezzo, Reinmar von Hagenau, Balakirev, Balanchivadze...):
fetch_wikidata_relationships.py's old extract_dates() claim-resolution,
verify_exact_agreeing_dates.py's separate exact-claim resolution, and
load_composers.py's free-text CSV parser -- plus approximate_dates.py,
an orphaned century-text parser that was never actually wired into any
of them, so "10th century" in CSV text used to parse to nothing at all.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import NamedTuple


@dataclass(frozen=True)
class DateEstimate:
    """Matches composers.birth_year/birth_year_upper/birth_precision (and
    the death_* equivalents) exactly -- callers can spread this straight
    into their SQL params. year_upper is None for a single-year value
    (exact/circa/before/after/unknown); only 'range' ever sets it."""
    year: int
    year_upper: int | None
    precision: str  # 'exact' | 'circa' | 'before' | 'after' | 'range' | 'unknown'

    def as_tuple(self) -> tuple:
        """(year, year_upper, precision) -- the plain tuple shape callers
        used before DateEstimate existed (composers.birth_year/
        _year_upper/_precision are still three separate DB columns), for
        call sites that just want to unpack straight into SQL params."""
        return self.year, self.year_upper, self.precision


class Ambiguous:
    """Sentinel: there genuinely isn't one answer to resolve to -- e.g.
    two differently-ranked-or-not Wikidata claims that disagree, or a
    century/millennium claim whose raw value is an exact block boundary
    (see resolve_wd_claims). Distinct from None (no claims at all)."""


AMBIGUOUS = Ambiguous()


class WDClaim(NamedTuple):
    """One non-deprecated Wikidata time claim, already reduced to plain
    values by the caller (fetch_wikidata_relationships.py knows how to
    read entity["claims"][prop] -- this module never does). month/day are
    None when the claim's own precision doesn't go that fine."""
    year: int
    month: int | None
    day: int | None
    precision: int  # Wikidata's own scale: 6=millennium 7=century 8=decade 9=year 10=month 11=day
    rank: str       # 'preferred' | 'normal' (deprecated claims must be filtered out by the caller)
    calendar: str | None  # 'gregorian' | 'julian' | None


# Wikidata time-value precision -> this repo's date_precision enum block
# size. 11=day/10=month/9=year all resolve to a single known year
# (year_upper stays None); 8=decade/7=century/6=millennium each get a
# computed block.
_YEAR_PRECISION_SPANS = {9: 0, 10: 0, 11: 0, 8: 9, 7: 99, 6: 999}

# Days to ADD to a Julian-calendar date to get its Gregorian equivalent
# (_JULIAN_TO_GREGORIAN_OFFSET), or to SUBTRACT from a Gregorian-calendar
# date to get its Julian equivalent (_GREGORIAN_TO_JULIAN_OFFSET). These
# are NOT mirror images of each other keyed on the same boundary dates:
# the offset widens by one day starting 1 March *Julian* of 1700/1800/
# 1900 -- the Julian calendar's unconditional every-4-years leap rule
# puts a 29 February in those years that the Gregorian calendar's every-
# 400-years exception skips -- but expressed in *Gregorian* terms that
# same real-world moment lands about a fortnight later (Julian 1 March
# 1700 is Gregorian 12 March 1700, not 1 March), since Gregorian has no
# corresponding leap day of its own to re-align against. A single table
# used for both directions (this module's original version) mis-converts
# any Gregorian-calendar composer date from 1 January up through the
# Gregorian-side cutoff of a boundary year -- verified against real
# composers with Julian Day Number arithmetic: Antonio Draghi (Gregorian
# death 16 Jan 1700 -- old code gave Julian 5 Jan, correct is 6 Jan) and
# Domenico Della-Maria (Gregorian death 9 Mar 1800 -- old code gave
# Julian 26 Feb, correct is 25 Feb). Also fixes the Julian-side case the
# boundary was originally meant for: Evald Aav (Julian birth 22 Feb 1900
# -> Gregorian 6 Mar 1900, not 7 Mar) and Isaak Dunayevsky (Julian birth
# 18 Jan 1900 -> Gregorian 30 Jan 1900, not 31 Jan). Pre-1700 lower
# bound is 1500, not the actual 1582 Gregorian reform date -- an existing,
# deliberate simplification: not needed for any composer this table would
# plausibly apply to anyway.
_JULIAN_TO_GREGORIAN_OFFSET = [
    ((1500, 1, 1), (1700, 2, 29), 10),
    ((1700, 3, 1), (1800, 2, 29), 11),
    ((1800, 3, 1), (1900, 2, 29), 12),
    ((1900, 3, 1), (2099, 12, 31), 13),
]
_GREGORIAN_TO_JULIAN_OFFSET = [
    ((1500, 1, 1), (1700, 3, 11), 10),
    ((1700, 3, 12), (1800, 3, 12), 11),
    ((1800, 3, 13), (1900, 3, 13), 12),
    ((1900, 3, 14), (2099, 12, 31), 13),
]


def _offset(year, month, day, from_calendar):
    table = _JULIAN_TO_GREGORIAN_OFFSET if from_calendar == "julian" else _GREGORIAN_TO_JULIAN_OFFSET
    key = (year, month, day)
    for lo, hi, offset in table:
        if lo <= key <= hi:
            return offset
    return None


def convert_calendar(d: date, from_calendar: str) -> date | None:
    """The equivalent date in the *other* calendar -- Julian in,
    Gregorian out, or vice versa -- or None when the offset tables above
    don't cover `d` (pre-1500) or from_calendar isn't "julian"/
    "gregorian". This is what a caller wanting Wikipedia's own "4 January
    1643 [O.S. 25 December 1642]" display convention (Newton, Washington,
    Stravinsky -- consistently Gregorian first, Julian/"Old Style"
    bracketed) needs: composers.birth_date/birth_calendar already store
    one side of the pair, this computes the other side on demand for
    *any* Julian-era composer, not just the ones where Wikidata happens
    to carry both claims independently (a much smaller set -- only 60
    composers in this repo's own data, see _calendar_equivalent_years
    below, which only ever gets to compare two *already-given* claims)."""
    if from_calendar not in ("julian", "gregorian"):
        return None
    offset = _offset(d.year, d.month, d.day, from_calendar)
    if offset is None:
        return None
    if from_calendar == "julian":
        return d + timedelta(days=offset)
    return d - timedelta(days=offset)


def _calendar_equivalent_years(claims: list[WDClaim]) -> set[int] | None:
    """When there are exactly two day-precision claims -- one Julian, one
    Gregorian -- and converting the Julian date lands exactly on the
    Gregorian date (via convert_calendar above), they describe the *same
    real-world day*, not a disagreement (e.g. Mily Balakirev/Q185040:
    Julian 1836-12-21 converts to Gregorian 1837-01-02, exactly matching
    the other claim -- the well-known Old Style/New Style pair for his
    birthdate). Returns {julian_year, gregorian_year} -- matching
    *either* one counts as agreement, since real sources use both
    conventions inconsistently (Balakirev's own source text says the
    Gregorian 1837, Balanchivadze's says the Julian 1862; neither is
    "more correct") -- or None if this doesn't apply. Not a general
    date-equivalence checker, just this one narrow, verifiable pattern."""
    day_claims = [c for c in claims if c.precision == 11 and c.month and c.day]
    julian = [c for c in day_claims if c.calendar == "julian"]
    gregorian = [c for c in day_claims if c.calendar == "gregorian"]
    if len(julian) != 1 or len(gregorian) != 1:
        return None
    try:
        jdate = date(julian[0].year, julian[0].month, julian[0].day)
        gdate = date(gregorian[0].year, gregorian[0].month, gregorian[0].day)
    except ValueError:
        return None
    if convert_calendar(jdate, "julian") == gdate:
        return {jdate.year, gdate.year}
    return None


def resolve_wd_claims(claims: list[WDClaim]) -> DateEstimate | Ambiguous | None:
    """The single "what do we believe" resolution for one property's
    (P569 or P570) full claim set. None means no usable claims at all;
    AMBIGUOUS means claims exist but don't resolve to one answer -- both
    are "we don't know", but kept distinct so callers can log/count them
    differently (a composer with zero claims vs. one with a genuine,
    visible dispute are different situations to review).

    Order of resolution:
    1. Day-precision (11) claims -- preferred rank wins outright even
       when a merely-normal-rank claim disagrees (real case: Maddalena
       Laura Sirmen's P569 had a normal-rank 1735 imported from enwiki
       alongside a preferred-rank 1745 sourced to BnF + Grove Music
       Online). Falls back to the first valid claim when there's no
       preferred one, or several -- not a guarantee of correctness, just
       deterministic and better than ignoring rank entirely. Applies to
       the day-precision tier and the coarser tier identically (a real
       bug in an earlier draft of this function only applied this
       properly to the coarser tier -- two *day-precision* claims that
       are both "preferred" but disagree, e.g. Pietro Antonio Fiocco/
       Q771208's 1653 and 1654, must not be silently resolved to
       whichever happens to sort first).
    2. Within whichever tier won step 1 (day, or coarser if there's no
       day-precision claim at all): if nothing carries "preferred" (or
       everything does but they agree), fall back to a. every claim
       already agreeing (unanimous), then b. the Julian/Gregorian same-
       day pattern above -- both apply at day precision too (Mily
       Balakirev's Julian/Gregorian pair *is* two day-precision claims).
    3. Century/decade/millennium block math for whichever single claim
       won steps 1-2. Century and millennium use the ordinal (no-year-0)
       convention Wikipedia itself states explicitly ("the 17th century
       lasted from January 1, 1601 ... to December 31, 1700"): a raw
       year ending in ...01 is the *start* of the following block, one
       ending in ...00 is the *end* of the current one, anything else
       falls wherever it numerically lands -- e.g. "1150" (Albertus
       Parisiensis/Q376521, confirmed on Wikidata's own page as "12th
       century") -> 1101-1200; "1000" (Odo of Arezzo/Q2438702, whose own
       source text says "10th century") -> 901-1000; "1200" (Reinmar von
       Hagenau/Q7310404, whose flourish/death data rules out 1200-1299
       entirely) -> 1101-1200. No case is genuinely ambiguous under this
       convention -- a round-hundred value determines which side of the
       boundary it's on from the number itself. Decades keep the
       existing floor convention instead (span=9): nobody counts decades
       ordinally from year 1, "the 1980s" is unambiguously 1980-1989.

    See resolve_winning_claim for a variant returning the winning
    WDClaim itself (with month/day/calendar intact) instead of a
    DateEstimate -- steps 1-2 above are shared between the two."""
    winner = resolve_winning_claim(claims)
    if winner is None:
        return None
    if winner is AMBIGUOUS:
        return AMBIGUOUS

    span = _YEAR_PRECISION_SPANS[winner.precision]
    if span == 0:
        return DateEstimate(year=winner.year, year_upper=None, precision="exact")

    block = span + 1
    if winner.precision == 8:
        # Decade: floor convention (no year-zero ordinal counting for decades).
        block_start = (winner.year // block) * block
        block_end = block_start + span
    else:
        # Century/millennium: ordinal (no-year-0) convention.
        block_number = ((winner.year - 1) // block) + 1
        block_start = (block_number - 1) * block + 1
        block_end = block_number * block
    return DateEstimate(year=block_start, year_upper=block_end, precision="range")


def resolve_winning_claim(claims: list[WDClaim]) -> WDClaim | Ambiguous | None:
    """Steps 1-2 of resolve_wd_claims' docstring, returning the winning
    WDClaim itself (month/day/calendar intact) rather than collapsing it
    into a DateEstimate -- for a caller that needs the full claim, e.g.
    to also record which calendar a day-precision claim was in
    (fetch_wikidata_relationships.py's birth_calendar/death_calendar).
    resolve_wd_claims is the right choice for everything else; this is
    the lower-level piece it's built on. See resolve_winning_claim_with_
    reason for a variant that also says *why* it won."""
    result = resolve_winning_claim_with_reason(claims)
    if result is None or result is AMBIGUOUS:
        return result
    claim, _reason = result
    return claim


def resolve_winning_claim_with_reason(claims: list[WDClaim]) -> tuple[WDClaim, str] | Ambiguous | None:
    """Same as resolve_winning_claim, but also returns *why* it won:
    "preferred" (a single claim carries Wikidata's preferred rank),
    "unanimous" (every claim in the tier already agrees), or
    "calendar_equivalent" (the Julian/Gregorian same-day pattern) -- for
    a caller building a human-readable explanation (verify_exact_
    agreeing_dates.py's auto-generated notes)."""
    if not claims:
        return None
    day_claims = [c for c in claims if c.precision == 11]
    tier = day_claims or [c for c in claims if c.precision in _YEAR_PRECISION_SPANS]
    if not tier:
        return None
    return _resolve_tier(tier) or AMBIGUOUS


def _resolve_tier(claims: list[WDClaim]) -> tuple[WDClaim, str] | None:
    """The shared preferred/unanimous/calendar-equivalent resolution,
    applied to one precision tier (all-day-precision, or all-coarser) --
    None means nothing in this tier resolves to one answer."""
    by_day = claims[0].precision == 11

    def key(c):
        return (c.year, c.month, c.day) if by_day else c.year

    preferred = [c for c in claims if c.rank == "preferred"]
    preferred_keys = {key(c) for c in preferred}
    if len(preferred_keys) == 1:
        return preferred[0], "preferred"
    if preferred_keys:
        return None  # multiple disagreeing preferred claims -- a real tie

    keys = {key(c) for c in claims}
    if len(keys) == 1:
        return claims[0], "unanimous"

    calendar_years = _calendar_equivalent_years(claims)
    if calendar_years is not None:
        # Both years describe the same real day -- report the Gregorian
        # side as the canonical pick (international convention), not
        # whichever happened to sort first; both claims are day-precision
        # by construction here (_calendar_equivalent_years only returns
        # non-None for a Julian+Gregorian day-precision pair).
        candidates = [c for c in claims if c.year in calendar_years]
        gregorian = [c for c in candidates if c.calendar == "gregorian"]
        return (gregorian[0] if gregorian else candidates[0]), "calendar_equivalent"
    return None


# --- Free-text (CSV) parsing -------------------------------------------

_YEAR_TOKEN = r"(\d{3,4})"
_RANGE_RE = re.compile(rf"^{_YEAR_TOKEN}\s*/\s*{_YEAR_TOKEN}$")
_BEFORE_RE = re.compile(rf"^before\s+{_YEAR_TOKEN}$", re.IGNORECASE)
_AFTER_RE = re.compile(rf"^after\s+{_YEAR_TOKEN}$", re.IGNORECASE)
_CIRCA_RE = re.compile(rf"^c\.?a?\.?\s*{_YEAR_TOKEN}\??$", re.IGNORECASE)
# A bare 3-digit year followed by '?' (e.g. "198?", "175?") is source
# shorthand for "this decade, exact year unknown" -- the leading digit of
# the 4-digit year is omitted and the '?' stands in for the missing last
# digit, so "198?" means 1980-1989, not "circa year 198". A 4-digit year
# + '?' (e.g. "1899?") is the ordinary circa case (_PLAIN_RE below).
_DECADE_RE = re.compile(r"^(\d{3})\?$")
_PLAIN_RE = re.compile(rf"^{_YEAR_TOKEN}(\?)?$")
_ANY_YEAR_RE = re.compile(_YEAR_TOKEN)
# "Nth century" / "early Nth century" / "late Nth century" -- merged in
# from the previously-orphaned approximate_dates.py, which no CSV-parsing
# caller ever actually used, so text like "10th century" used to parse to
# nothing at all despite being common in medieval-composer source lists.
_CENTURY_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)\s+century", re.IGNORECASE)


def parse_free_text(raw) -> DateEstimate | None:
    """Parse a birth/death source-list field (English prose, not
    Wikidata JSON) into a DateEstimate, or None if nothing recognizable
    is in it. raw may be None, NaN (pandas), or any non-string -- treated
    the same as empty."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None

    m = _RANGE_RE.match(text)
    if m:
        return DateEstimate(int(m.group(1)), int(m.group(2)), "range")

    m = _BEFORE_RE.match(text)
    if m:
        return DateEstimate(int(m.group(1)), None, "before")

    m = _AFTER_RE.match(text)
    if m:
        return DateEstimate(int(m.group(1)), None, "after")

    m = _CIRCA_RE.match(text)
    if m:
        return DateEstimate(int(m.group(1)), None, "circa")

    m = _DECADE_RE.match(text)
    if m:
        decade = int(m.group(1)) * 10
        return DateEstimate(decade, decade + 9, "range")

    m = _PLAIN_RE.match(text)
    if m:
        return DateEstimate(int(m.group(1)), None, "circa" if m.group(2) else "exact")

    m = _CENTURY_RE.search(text)
    if m:
        # Ordinal (no-year-0) convention, same as resolve_wd_claims'
        # century block math -- "10th century" = 901-1000, matching
        # Wikipedia's own stated definition of a century's span.
        century = int(m.group(1))
        start, end = (century - 1) * 100 + 1, century * 100
        lower = text.lower()
        if "second half" in lower or "late" in lower:
            return DateEstimate(start + 50, end, "range")
        if "first half" in lower or "early" in lower:
            return DateEstimate(start, start + 49, "range")
        return DateEstimate(start, end, "range")

    m = _ANY_YEAR_RE.search(text)
    if m:
        return DateEstimate(int(m.group(1)), None, "unknown")

    return DateEstimate(year=None, year_upper=None, precision="unknown")


def approximate_year(estimate: DateEstimate | None) -> int | None:
    """A single sortable year for display/estimation purposes -- the
    midpoint of a range, or the year itself for a point value. Kept
    separate from DateEstimate/parse_free_text: this is a display
    concern for callers that need one comparable number (e.g. sorting a
    list by approximate birth year), not a parsing concern."""
    if estimate is None or estimate.year is None:
        return None
    if estimate.year_upper is None:
        return estimate.year
    return (estimate.year + estimate.year_upper) // 2


def estimate_year(year, year_upper, raw) -> int | None:
    """One best-guess sortable year from a composer's stored columns,
    falling back to parsing raw text only when year is NULL --
    birth_year/birth_year_upper win whenever birth_year is set (raw is
    the original source text whether or not anything was ever extracted
    from it; year is only set once something concrete was, from that
    text or a later Wikidata backfill). Matches the previously-orphaned
    approximate_dates.py's estimate_birth_year(), except the raw-text
    fallback now goes through the full parse_free_text() (any pattern it
    recognizes) rather than century-phrases only -- that old restriction
    was just an artifact of century_to_year_range() never having been
    merged with the rest of the CSV parser, not a deliberate scope
    limit, so there's no reason to keep it narrower now that they're
    unified."""
    if year is not None:
        return approximate_year(DateEstimate(year, year_upper, "range" if year_upper else "exact"))
    return approximate_year(parse_free_text(raw))


def as_tuple(estimate: DateEstimate | None) -> tuple:
    """Same as DateEstimate.as_tuple(), but also handles the common
    Optional case (parse_free_text/estimate_year-adjacent callers often
    have "no estimate at all" to account for, and None has no method to
    call) -- (None, None, None) when there's no estimate."""
    return estimate.as_tuple() if estimate is not None else (None, None, None)


def is_pre_verified(row: dict, field: str) -> bool:
    """True if row[f"{field}_year_verified"] is already set -- a named
    wrapper for the "never touch a hand-verified row" policy, so it's one
    function instead of a copy-pasted inline check per script. field is
    "birth" or "death"."""
    return bool(row.get(f"{field}_year_verified"))
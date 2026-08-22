import pytest

from datetime import date

from domain.dates import (
    AMBIGUOUS,
    DateEstimate,
    WDClaim,
    approximate_year,
    as_tuple,
    convert_calendar,
    estimate_year,
    is_pre_verified,
    parse_free_text,
    resolve_wd_claims,
)


def wd(year, precision, rank="normal", month=None, day=None, calendar=None):
    return WDClaim(year=year, month=month, day=day, precision=precision, rank=rank, calendar=calendar)


# --- convert_calendar ---------------------------------------------------

def test_convert_calendar_julian_to_gregorian():
    # Mily Balakirev/Q185040.
    assert convert_calendar(date(1836, 12, 21), "julian") == date(1837, 1, 2)


def test_convert_calendar_gregorian_to_julian():
    assert convert_calendar(date(1837, 1, 2), "gregorian") == date(1836, 12, 21)


def test_convert_calendar_isaac_newton():
    # en.wikipedia: "4 January 1643 [O.S. 25 December 1642]".
    assert convert_calendar(date(1642, 12, 25), "julian") == date(1643, 1, 4)


def test_convert_calendar_pre_1500_unsupported():
    assert convert_calendar(date(1400, 1, 1), "julian") is None


def test_convert_calendar_unknown_calendar():
    assert convert_calendar(date(1800, 1, 1), "french_republican") is None


def test_convert_calendar_julian_before_1900_boundary():
    # Evald Aav/Q1218538: 22 Feb 1900 (Julian) -> 6 Mar 1900, not 7 Mar --
    # the 13-day offset only starts 1 March (Julian).
    assert convert_calendar(date(1900, 2, 22), "julian") == date(1900, 3, 6)


def test_convert_calendar_julian_on_1900_boundary():
    # Isaak Dunayevsky/Q4276925: 18 Jan 1900 (Julian) -> 30 Jan 1900.
    assert convert_calendar(date(1900, 1, 18), "julian") == date(1900, 1, 30)


def test_convert_calendar_julian_after_1900_boundary():
    assert convert_calendar(date(1900, 3, 1), "julian") == date(1900, 3, 14)


def test_convert_calendar_gregorian_before_1700_boundary():
    # Antonio Draghi/Q76564: 16 Jan 1700 (Gregorian) -> 6 Jan 1700 (Julian),
    # still the old 10-day offset, not the 11-day one that starts later
    # in Gregorian terms (12 Mar 1700) than the Julian-side boundary
    # (1 Mar 1700) would suggest.
    assert convert_calendar(date(1700, 1, 16), "gregorian") == date(1700, 1, 6)


def test_convert_calendar_gregorian_just_before_1700_gregorian_side_cutoff():
    # Diogo Dias Melgás/Q3705153: 10 Mar 1700 (Gregorian) -> 28 Feb 1700
    # (Julian) -- still offset 10, even though the naive Julian-side
    # cutoff (1 Mar) has already passed.
    assert convert_calendar(date(1700, 3, 10), "gregorian") == date(1700, 2, 28)


def test_convert_calendar_gregorian_after_1700_gregorian_side_cutoff():
    # Michel Blavet/Q3618366: 13 Mar 1700 (Gregorian) -> 2 Mar 1700 (Julian).
    assert convert_calendar(date(1700, 3, 13), "gregorian") == date(1700, 3, 2)


def test_convert_calendar_gregorian_just_before_1800_gregorian_side_cutoff():
    # Domenico Della-Maria/Q1273541: 9 Mar 1800 (Gregorian) -> 26 Feb 1800
    # (Julian) -- still offset 11.
    assert convert_calendar(date(1800, 3, 9), "gregorian") == date(1800, 2, 26)


def test_convert_calendar_roundtrip_across_1700_boundary():
    for m, d in [(1, 16), (2, 28), (3, 10), (3, 13), (12, 25)]:
        g = date(1700, m, d)
        j = convert_calendar(g, "gregorian")
        assert convert_calendar(j, "julian") == g


# --- resolve_wd_claims: day-precision ---------------------------------

def test_resolve_no_claims():
    assert resolve_wd_claims([]) is None


def test_resolve_single_day_claim():
    assert resolve_wd_claims([wd(1856, 11, month=8, day=31)]) == DateEstimate(1856, None, "exact")


def test_resolve_day_preferred_wins_over_normal():
    # Maddalena Laura Sirmen: normal-rank 1735 (imported from enwiki)
    # alongside preferred-rank 1745 (BnF + Grove Music Online).
    claims = [wd(1735, 11, rank="normal", month=1, day=1), wd(1745, 11, rank="preferred", month=1, day=1)]
    assert resolve_wd_claims(claims) == DateEstimate(1745, None, "exact")


def test_resolve_day_unanimous_normal_claims():
    claims = [wd(1856, 11, rank="normal", month=8, day=31), wd(1856, 11, rank="normal", month=8, day=31)]
    assert resolve_wd_claims(claims) == DateEstimate(1856, None, "exact")


def test_resolve_day_two_disagreeing_preferred_claims_is_ambiguous():
    # Pietro Antonio Fiocco/Q771208: 1650 normal (year precision), plus
    # TWO different day-precision claims that are BOTH preferred (1653,
    # 1654) -- a real tie Wikidata's own rank system doesn't resolve,
    # not something to silently pick one side of.
    claims = [wd(1650, 9, rank="normal"), wd(1653, 11, rank="preferred", month=1, day=1),
              wd(1654, 11, rank="preferred", month=1, day=1)]
    assert resolve_wd_claims(claims) is AMBIGUOUS


def test_resolve_day_normal_claims_disagree_no_preferred_is_ambiguous():
    claims = [wd(1735, 11, rank="normal", month=1, day=1), wd(1745, 11, rank="normal", month=1, day=1)]
    assert resolve_wd_claims(claims) is AMBIGUOUS


def test_resolve_calendar_equivalent_julian_gregorian():
    # Mily Balakirev/Q185040: Julian 1836-12-21 == Gregorian 1837-01-02.
    claims = [
        wd(1836, 11, rank="normal", month=12, day=21, calendar="julian"),
        wd(1837, 11, rank="normal", month=1, day=2, calendar="gregorian"),
    ]
    assert resolve_wd_claims(claims) == DateEstimate(1837, None, "exact")


def test_resolve_non_equivalent_julian_gregorian_pair_is_ambiguous():
    claims = [
        wd(1836, 11, rank="normal", month=1, day=1, calendar="julian"),
        wd(1900, 11, rank="normal", month=6, day=15, calendar="gregorian"),
    ]
    assert resolve_wd_claims(claims) is AMBIGUOUS


# --- resolve_wd_claims: year precision (no block math) ------------------

def test_resolve_year_preferred_wins_over_normal():
    # Wang Xilin/Q7967693: preferred 1936 vs. unsourced normal 1937 (both
    # actually day-precision in reality, but year-precision-only claims
    # follow the identical preferred/unanimous rule).
    claims = [wd(1937, 9, rank="normal"), wd(1936, 9, rank="preferred")]
    assert resolve_wd_claims(claims) == DateEstimate(1936, None, "exact")


def test_resolve_year_unanimous_claims():
    claims = [wd(1150, 9, rank="normal"), wd(1150, 9, rank="normal")]
    assert resolve_wd_claims(claims) == DateEstimate(1150, None, "exact")


def test_resolve_year_two_normal_claims_disagree_is_ambiguous():
    # Semyon Panchenko/Q27732062: 1867 vs. 1887, neither preferred.
    claims = [wd(1867, 9, rank="normal"), wd(1887, 9, rank="normal")]
    assert resolve_wd_claims(claims) is AMBIGUOUS


# --- resolve_wd_claims: century/decade/millennium block math -----------
#
# Century/millennium use the ordinal (no-year-0) convention Wikipedia
# itself states explicitly ("the 17th century lasted from January 1,
# 1601 ... to December 31, 1700"): century_number = ((year-1)//100)+1,
# spanning [(century_number-1)*100+1, century_number*100]. A round-
# hundred raw value isn't ambiguous under this convention -- it's always
# either the *start* of the next century (...01) or the *end* of the
# current one (...00), determined by the number itself, not a guess.
# Decades keep the existing floor convention (span=9): nobody counts
# decades ordinally from year 1, "the 1980s" is unambiguously 1980-1989.

def test_resolve_mid_century():
    # Albertus Parisiensis/Q376521: "1150" at century precision is
    # Wikidata's own rendering of "12th century" (confirmed directly on
    # Wikidata's own page), not literally 1150.
    assert resolve_wd_claims([wd(1150, 7)]) == DateEstimate(1101, 1200, "range")


def test_resolve_century_ending_in_00_is_end_of_that_century():
    # Odo of Arezzo/Q2438702: his own source text says "10th century";
    # 1000 is the last year of the 10th century under the ordinal
    # convention, not the first year of an 11th-century block.
    assert resolve_wd_claims([wd(1000, 7)]) == DateEstimate(901, 1000, "range")


def test_resolve_century_ending_in_00_reinmar_case():
    # Reinmar von Hagenau/Q7310404: flourish 1185-1205 and death c.1210
    # both require birth to be in the 1100s, not 1200-1299 -- resolves
    # cleanly to 1101-1200 under the ordinal convention, no contradiction.
    assert resolve_wd_claims([wd(1200, 7)]) == DateEstimate(1101, 1200, "range")


def test_resolve_century_starting_at_01_is_start_of_next_century():
    assert resolve_wd_claims([wd(1301, 7)]) == DateEstimate(1301, 1400, "range")


def test_resolve_millennium():
    assert resolve_wd_claims([wd(2000, 6)]) == DateEstimate(1001, 2000, "range")


def test_resolve_mid_decade_floors_to_block():
    assert resolve_wd_claims([wd(1983, 8)]) == DateEstimate(1980, 1989, "range")


# --- parse_free_text -----------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    (None, None),
    ("", None),
    ("1650", DateEstimate(1650, None, "exact")),
    ("1650?", DateEstimate(1650, None, "circa")),
    ("c. 1650", DateEstimate(1650, None, "circa")),
    ("ca. 1650", DateEstimate(1650, None, "circa")),
    ("before 1700", DateEstimate(1700, None, "before")),
    ("after 1600", DateEstimate(1600, None, "after")),
    ("1650/1750", DateEstimate(1650, 1750, "range")),
    ("198?", DateEstimate(1980, 1989, "range")),
    ("10th century", DateEstimate(901, 1000, "range")),
    ("14th century", DateEstimate(1301, 1400, "range")),
    ("late 15th century", DateEstimate(1451, 1500, "range")),
])
def test_parse_free_text_basic(text, expected):
    assert parse_free_text(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("early 16th century", DateEstimate(1501, 1550, "range")),
    ("second half of the 14th century", DateEstimate(1351, 1400, "range")),
    ("later 17th century", DateEstimate(1651, 1700, "range")),
])
def test_parse_free_text_century_qualifiers(text, expected):
    assert parse_free_text(text) == expected


def test_parse_free_text_unparseable_but_has_a_year():
    assert parse_free_text("fl. 1500s") == DateEstimate(1500, None, "unknown")


def test_parse_free_text_nothing_recognizable():
    assert parse_free_text("?") == DateEstimate(None, None, "unknown")


# --- approximate_year / estimate_year -----------------------------------

@pytest.mark.parametrize("estimate,expected", [
    (DateEstimate(1235, 1255, "range"), 1245),
    (DateEstimate(1235, None, "exact"), 1235),
    (None, None),
])
def test_approximate_year(estimate, expected):
    assert approximate_year(estimate) == expected


@pytest.mark.parametrize("year,year_upper,raw,expected", [
    # year set -> used directly, raw ignored.
    (1700, None, "early 18th century", 1700),
    (1235, 1255, None, 1245),
    # year NULL -> falls back to parsing raw.
    (None, None, "10th century", 950),  # (901+1000)//2
    (None, None, "1804", 1804),
    (None, None, "?", None),
    (None, None, None, None),
])
def test_estimate_year(year, year_upper, raw, expected):
    assert estimate_year(year, year_upper, raw) == expected


# --- as_tuple -------------------------------------------------------------

def test_date_estimate_as_tuple_method():
    assert DateEstimate(1650, 1659, "range").as_tuple() == (1650, 1659, "range")


def test_as_tuple_handles_none():
    assert as_tuple(None) == (None, None, None)


def test_as_tuple_handles_estimate():
    assert as_tuple(DateEstimate(1650, None, "exact")) == (1650, None, "exact")


# --- is_pre_verified -----------------------------------------------------

def test_is_pre_verified():
    assert is_pre_verified({"birth_year_verified": True}, "birth") is True
    assert is_pre_verified({"birth_year_verified": False}, "birth") is False
    assert is_pre_verified({"death_year_verified": None}, "death") is False
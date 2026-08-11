import pytest

from approximate_dates import approximate_birth_year, century_to_year_range, estimate_birth_year


@pytest.mark.parametrize(
    "year,year_end,expected",
    [
        (1235, 1255, 1245),
        (1235, None, 1235),
        (None, None, None),
    ])
def test_approximate_birth_year(year, year_end, expected):
    assert approximate_birth_year(year, year_end) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10th century", (900, 1000)),
        ("14th century", (1300, 1400)),
        ("late 15th century", (1450, 1500)),
        ("early 16th century", (1500, 1550)),
        ("second half of the 14th century", (1350, 1400)),
        ("later 17th century", (1650, 1700)),
        ("1804", (None, None)),
        (None, (None, None)),
    ])
def test_century_to_year_range(text, expected):
    assert century_to_year_range(text) == expected


@pytest.mark.parametrize(
    "year,year_end,raw,expected",
    [
        # birth_year set -> used directly, birth_raw ignored (composer
        # 1590: birth_year=1700 from a Wikidata backfill even though
        # birth_raw is the unparsed "early 18th century").
        (1700, None, "early 18th century", 1700),
        (1235, 1255, None, 1245),
        # birth_year NULL -> falls back to parsing birth_raw as a century
        # phrase (composers 7/102/303/421/651/1587 from the DB sample).
        (None, None, "10th century", 950),
        (None, None, "14th century", 1350),
        (None, None, "late 15th century", 1475),
        (None, None, "early 16th century", 1525),
        (None, None, "second half of the 14th century", 1375),
        (None, None, "later 17th century", 1675),
        # birth_year NULL and birth_raw not a parseable century phrase.
        (None, None, "?", None),
        (None, None, None, None),
    ])
def test_estimate_birth_year(year, year_end, raw, expected):
    assert estimate_birth_year(year, year_end, raw) == expected

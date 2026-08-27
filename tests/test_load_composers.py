from load_composers import looks_like_different_person


# --- looks_like_different_person -----------------------------------------
# Real calibration cases, verified against Wikidata/Wikipedia directly
# (2026-08-23) -- see load_composers.py's own comment above
# TOLERANCE_SCALE for the sourcing behind each one.

def test_same_person_historical_sourcing_disagreement():
    # Pomponio Nenna (composer 562, Q3907903): en.wikipedia gives
    # 1556-1608; one of this repo's own CSVs has "c. 1550"-1613 for the
    # same real person.
    assert looks_like_different_person(1556, 1608, 1550, 1613) is False


def test_different_person_small_gap_documented_namesake():
    # Jean-Marie Leclair l'aine (1551, Q348875) vs. le cadet/"the younger"
    # (1613, Q6169629) -- a documented nephew, distinct QID, only a
    # 6/13-year gap. The case that caught an over-loose first calibration
    # (TOLERANCE_SCALE=0.35 with round() wrongly called this "same").
    assert looks_like_different_person(1697, 1764, 1703, 1777) is True


def test_different_person_large_gap():
    # Louis Aubert: an 1720-1800 composer and an entirely separate
    # 1877-1968 one share the name (confirmed via distinct Wikipedia
    # articles) -- 80+ years apart, unambiguous at any era.
    assert looks_like_different_person(1720, 1800, 1877, 1968) is True


def test_same_person_small_gap_existing_db_pair():
    # Gasparo Alberti (composers 485/9669) -- an existing duplicate pair
    # in the DB, only one real Wikipedia article for the name, 4/5-year
    # gap -- should resolve to "same" like Nenna, not "different".
    assert looks_like_different_person(1489, 1560, 1485, 1565) is False


def test_modern_composer_small_gap_is_different():
    # A 20th/21st-century composer's dates are ordinarily precise -- even
    # a few years apart most likely means two different real people (see
    # James Lavino: one born 1937, an entirely different one born 1973,
    # already unambiguous under any tolerance since they only have a
    # birth year -- this is the harder near-miss case with both dates
    # known and only a small gap).
    assert looks_like_different_person(2010, 2020, 2013, 2023) is True


def test_missing_death_year_falls_back_to_large_birth_gap():
    # Neither side has a death year -- LARGE_BIRTH_GAP (15), not the
    # scaled tolerance, decides.
    assert looks_like_different_person(1937, None, 1973, None) is True
    assert looks_like_different_person(1937, None, 1940, None) is False

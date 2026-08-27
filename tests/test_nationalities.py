from domain.nationalities import (
    CITIZENSHIP_TO_NATIONALITY,
    MIN_BIRTHPLACE_SUGGESTION_YEAR,
    MIN_RELATION_DISCOVERY_COMPOSER_ID,
    NEED_TO_CHECK_EXCEPTIONS,
    VERIFIED_NOT_NEEDING_CHECK,
    VOLATILE_BIRTH_COUNTRIES,
    predict_need_to_check,
    suggest_nationality_from_birthplace,
)


# --- predict_need_to_check ------------------------------------------------

def test_relation_discovery_single_claim_matches():
    qid, nat = next(iter(CITIZENSHIP_TO_NATIONALITY.items()))
    composer_id = MIN_RELATION_DISCOVERY_COMPOSER_ID
    assert predict_need_to_check(composer_id, "Q_some_composer", nat, [qid]) is True


def test_ordinary_csv_composer_not_flagged_despite_matching_claim():
    # Below the relation-discovery boundary, a matching citizenship claim
    # is just normal, correctly-sourced data, not evidence of an
    # unverified bulk assignment -- must not fire.
    qid, nat = next(iter(CITIZENSHIP_TO_NATIONALITY.items()))
    composer_id = MIN_RELATION_DISCOVERY_COMPOSER_ID - 1
    assert predict_need_to_check(composer_id, "Q_some_composer", nat, [qid]) is False


def test_multiple_citizenship_claims_not_predicted():
    # Multi-citizenship composers in the relation-discovery batch were
    # individually researched (per nationality_citizenship_review.md),
    # so the bare claim-count rule shouldn't fire even above the boundary.
    qid, nat = next(iter(CITIZENSHIP_TO_NATIONALITY.items()))
    composer_id = MIN_RELATION_DISCOVERY_COMPOSER_ID
    assert predict_need_to_check(composer_id, "Q_some_composer", nat, [qid, "Q_other"]) is False


def test_no_citizenship_claim_not_predicted():
    composer_id = MIN_RELATION_DISCOVERY_COMPOSER_ID
    assert predict_need_to_check(composer_id, "Q_some_composer", "German", []) is False


def test_verified_exclusion_overrides_matching_claim():
    # Theodor Kullak: matches CITIZENSHIP_TO_NATIONALITY exactly but was
    # confirmed NOT flagged in the recovered backup -- verified by hand
    # at some point, must stay excluded even above the boundary.
    wikidata_id = next(iter(VERIFIED_NOT_NEEDING_CHECK))
    # Find a QID that maps to a nationality, to build a would-otherwise-match case.
    qid, nat = next(iter(CITIZENSHIP_TO_NATIONALITY.items()))
    composer_id = MIN_RELATION_DISCOVERY_COMPOSER_ID
    assert predict_need_to_check(composer_id, wikidata_id, nat, [qid]) is False


def test_explicit_exception_fires_regardless_of_id():
    # Wipo of Burgundy (id 13, original CSV pipeline, well below the
    # relation-discovery boundary): his only citizenship claim maps to
    # "German" per CITIZENSHIP_TO_NATIONALITY, but his real nationality
    # is "Frankish (Arles/Burgundy)" -- an anachronistic P27 mapping.
    # Must be flagged via the explicit exception, not the claim rule.
    wikidata_id = "Q537218"
    assert wikidata_id in NEED_TO_CHECK_EXCEPTIONS
    assert predict_need_to_check(13, wikidata_id, "Frankish (Arles/Burgundy)", ["Q183"]) is True


def test_explicit_exception_does_not_fire_for_wrong_nationality_name():
    wikidata_id = "Q537218"
    assert predict_need_to_check(13, wikidata_id, "German", ["Q183"]) is False


def test_unknown_composer_not_predicted():
    assert predict_need_to_check(1, "Q_unknown_composer", "German", []) is False


# --- suggest_nationality_from_birthplace ----------------------------------

def test_suggests_from_stable_country_after_threshold():
    qid, nat = next(iter((q, n) for q, n in CITIZENSHIP_TO_NATIONALITY.items() if q not in VOLATILE_BIRTH_COUNTRIES))
    assert suggest_nationality_from_birthplace(MIN_BIRTHPLACE_SUGGESTION_YEAR, qid) == nat


def test_no_suggestion_before_threshold_year():
    # Abraham Megerle, ~1600s Salzburg -- an independent Prince-
    # Archbishopric at the time, not reliably "German" or "Austrian"
    # from birthplace alone.
    qid, nat = next(iter((q, n) for q, n in CITIZENSHIP_TO_NATIONALITY.items() if q not in VOLATILE_BIRTH_COUNTRIES))
    assert suggest_nationality_from_birthplace(1600, qid) is None


def test_no_suggestion_for_volatile_country_even_after_threshold():
    # Moritz Brosig (German, born in what's now Poland) and Bolesław
    # Woytowicz (Polish, born in what's now Ukraine) -- both well after
    # 1800, both wrong from birth-country alone.
    qid = next(iter(VOLATILE_BIRTH_COUNTRIES))
    assert suggest_nationality_from_birthplace(1900, qid) is None


def test_no_suggestion_for_unmapped_country():
    assert suggest_nationality_from_birthplace(1900, "Q_not_in_any_dict") is None


def test_no_suggestion_for_missing_birth_year_or_country():
    qid = next(iter(CITIZENSHIP_TO_NATIONALITY))
    assert suggest_nationality_from_birthplace(None, qid) is None
    assert suggest_nationality_from_birthplace(1900, None) is None


def test_year_boundary_is_inclusive():
    qid, nat = next(iter((q, n) for q, n in CITIZENSHIP_TO_NATIONALITY.items() if q not in VOLATILE_BIRTH_COUNTRIES))
    assert suggest_nationality_from_birthplace(MIN_BIRTHPLACE_SUGGESTION_YEAR - 1, qid) is None
    assert suggest_nationality_from_birthplace(MIN_BIRTHPLACE_SUGGESTION_YEAR, qid) == nat

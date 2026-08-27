from domain.tags import (
    EXCLUDED_QIDS,
    NAME_OVERRIDES,
    QID_REDIRECTS,
    resolve_tag_name,
    resolve_tag_qids,
)


# --- resolve_tag_qids ----------------------------------------------------

def test_resolve_tag_qids_keeps_a_real_movement():
    assert resolve_tag_qids(["Q248243"]) == ["Q248243"]  # Second Viennese School


def test_resolve_tag_qids_drops_excluded():
    excluded = next(iter(EXCLUDED_QIDS))
    assert resolve_tag_qids([excluded]) == []


def test_resolve_tag_qids_applies_redirect():
    redirected_from, redirected_to = next(iter(QID_REDIRECTS.items()))
    assert resolve_tag_qids([redirected_from]) == [redirected_to]


def test_resolve_tag_qids_redirect_targets_never_excluded():
    # A QID_REDIRECTS target landing in EXCLUDED_QIDS would make the
    # redirect pointless (it'd just get dropped again right after) --
    # every redirect must point somewhere that survives.
    for target in QID_REDIRECTS.values():
        assert target not in EXCLUDED_QIDS


def test_resolve_tag_qids_preserves_order_and_multiple_values():
    assert resolve_tag_qids(["Q248243", "Q1362030"]) == ["Q248243", "Q1362030"]


def test_resolve_tag_qids_mixes_keep_redirect_and_drop():
    redirected_from, redirected_to = next(iter(QID_REDIRECTS.items()))
    excluded = next(iter(EXCLUDED_QIDS))
    assert resolve_tag_qids(["Q248243", excluded, redirected_from]) == ["Q248243", redirected_to]


def test_resolve_tag_qids_empty_input():
    assert resolve_tag_qids([]) == []


# --- resolve_tag_name ------------------------------------------------------

def test_resolve_tag_name_override_wins_over_qid_labels():
    qid, expected = next(iter(NAME_OVERRIDES.items()))
    assert resolve_tag_name(qid, {qid: "some other wikidata label"}) == expected


def test_resolve_tag_name_falls_back_to_qid_labels():
    assert resolve_tag_name("Q248243", {"Q248243": "Second Viennese School"}) == "Second Viennese School"


def test_resolve_tag_name_falls_back_to_bare_qid():
    assert resolve_tag_name("Q99999999", {}) == "Q99999999"

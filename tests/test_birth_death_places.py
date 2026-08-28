from load_birth_death_places import _window_active, build_qid_windows


def _p1448(*entries):
    """entries: (start, end, language, name) tuples -> raw P1448 claim dicts."""
    return [
        {"start": start, "end": end, "language": language, "name": name, "rank": "normal"}
        for start, end, language, name in entries
    ]


def test_prefers_english_claim_when_present():
    claims = {"p17": [], "p1448": _p1448((None, None, "en", "Vienna"), (None, None, "de", "Wien"))}
    _, name_windows = build_qid_windows("Q1", claims, {"Q1": "Wien"})
    assert name_windows == [(None, None, "Vienna")]


def test_single_window_item_borrows_qid_labels_over_ru():
    # Liège: no "en" P1448 claim, only fr/de/nl/it/es/ru/... -- qid_labels
    # (Wikidata's own best-label pick) is trusted since there's only one
    # window, so there's no historical-era distinction to preserve.
    claims = {"p17": [], "p1448": _p1448(
        (None, None, "fr", "Liège"), (None, None, "de", "Lüttich"), (None, None, "ru", "Льеж"),
    )}
    _, name_windows = build_qid_windows("Q2", claims, {"Q2": "Liège"})
    assert name_windows == [(None, None, "Liège")]


def test_multi_window_item_only_borrows_qid_labels_for_open_window():
    # Regression case: Leningrad/Saint Petersburg (Q656) has four dated
    # name windows, none with an "en" P1448 claim. An earlier version of
    # this fix applied qid_labels ("Saint Petersburg", the *current* name)
    # to every window regardless of era, silently turning the 1924-1991
    # "Leningrad" window into "Saint Petersburg" too. Only the open-ended
    # (end=None) window may borrow qid_labels; closed historical windows
    # must keep using their own P1448 data even if that means falling back
    # to a non-English language.
    claims = {"p17": [], "p1448": _p1448(
        (1703, 1914, "ru", "Санкт-Петербург"),
        (1914, 1924, "ru", "Петроград"),
        (1924, 1991, "ru", "Ленинград"),
        (1924, 1991, "de", "Leningrad"),
        (1991, None, "ru", "Санкт-Петербург"),
    )}
    _, name_windows = build_qid_windows("Q656", claims, {"Q656": "Saint Petersburg"})
    by_window = {(s, e): name for s, e, name in name_windows}
    assert by_window[(1991, None)] == "Saint Petersburg"
    assert by_window[(1924, 1991)] != "Saint Petersburg"
    assert by_window[(1914, 1924)] != "Saint Petersburg"
    assert by_window[(1703, 1914)] != "Saint Petersburg"


def test_multi_window_item_with_no_qid_label_falls_back_to_ru_then_alphabetical():
    claims = {"p17": [], "p1448": _p1448(
        (None, 1945, "de", "Breslau"), (1945, None, "pl", "Wrocław"), (1945, None, "ru", "Вроцлав"),
    )}
    _, name_windows = build_qid_windows("Q3", claims, {})
    by_window = {(s, e): name for s, e, name in name_windows}
    assert by_window[(None, 1945)] == "Breslau"
    # No qid_label available at all -- still falls to the old "ru" then
    # alphabetical-language fallback for the window lacking English.
    assert by_window[(1945, None)] == "Вроцлав"


def test_no_p1448_claims_returns_none_name_windows():
    claims = {"p17": [{"start": None, "end": None, "country_qid": "Q40", "rank": "preferred"}], "p1448": []}
    country_windows, name_windows = build_qid_windows("Q4", claims, {"Q4": "Somewhere"})
    assert name_windows is None
    assert country_windows == [(None, None, "Q40")]


# --- _window_active ---------------------------------------------------

def test_narrowest_window_wins_over_an_earlier_open_ended_one():
    # Regression case found 2026-08-28: Pécs/Debrecen/Szeged/Eger/etc. all
    # collapsed their entire 1867-1989 regime chain into one
    # "Austria-Hungary" period. Wikidata's claim order is insertion order,
    # not chronological -- Austria-Hungary (start=1867, genuinely no P582
    # on Wikidata) was listed before the later, more specific claims
    # (Kingdom of Hungary 1920-1946, etc.), so the old "return the first
    # match" behavior let it silently win for every point up to 1989,
    # even though a narrower, more specific claim also covered that point.
    windows = [
        (1867, None, "Q28513"),          # Austria-Hungary -- open-ended, listed first
        (1920, 1946, "Q600018"),         # Kingdom of Hungary -- narrower, listed second
        (1946, 1949, "Q940741"),         # Second Hungarian Republic
    ]
    assert _window_active(windows, 1930) == "Q600018"
    assert _window_active(windows, 1947) == "Q940741"
    # Still correctly falls through to the open-ended claim wherever no
    # narrower window covers the point.
    assert _window_active(windows, 1900) == "Q28513"


def test_window_active_returns_none_when_nothing_matches():
    assert _window_active([(1920, 1946, "Q600018")], 1800) is None

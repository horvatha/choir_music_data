import json
from unittest.mock import patch

import pytest

import backfill_cache

# A composer whose qid is already cached, one whose isn't -- shape matches
# wikidata_relationships.json's real "composers" entries closely enough for
# the tests below (only "qid" is actually read by the cache-partitioning
# logic under test; the entity payload itself is opaque to it).
CACHED_ENTRY = {"qid": "Q1", "name": "Cached Composer"}
LIVE_ENTRY = {"qid": "Q2", "name": "Live Composer"}
FIXTURE_ENTITY = {"claims": {"P569": []}, "sitelinks": {}}


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    path = tmp_path / "wikidata_relationships.json"
    path.write_text(json.dumps({
        "composers": {"1": dict(CACHED_ENTRY), "2": dict(LIVE_ENTRY)},
        "qid_labels": {},
    }))
    monkeypatch.setattr(backfill_cache, "OUTPUT_FILE", str(path))
    return path


def _requested_ids(mock_api_get):
    """Every QID any api_get() call actually asked Wikidata for, across
    both the one-at-a-time and batched ("|"-joined) call shapes."""
    ids = set()
    for call in mock_api_get.call_args_list:
        params = call.args[1] if len(call.args) > 1 else call.kwargs["params"]
        ids.update(params["ids"].split("|"))
    return ids


@pytest.mark.parametrize("field", ["dates", "sitelinks", "attributes", "relationships"])
def test_cached_composer_never_hits_live_api(cache_file, field, monkeypatch):
    """Q1's qid is already cached -- it must be resolved via config["apply"]
    against the cached entity, and no live api_get() call may ever mention
    Q1's qid. Q2 isn't cached, so it must still go through api_get exactly
    as before this change."""
    config = backfill_cache.BACKFILL_FIELDS[field]
    applied = []
    monkeypatch.setitem(config, "apply", lambda e, entity, family: applied.append((e["qid"], entity, family)))

    def fake_fetch_entities(qids):
        assert set(qids) == {"Q1", "Q2"}
        return {"Q1": FIXTURE_ENTITY}  # only Q1 is cached

    with patch("backfill_cache.wikidata_entities_store.fetch_entities", side_effect=fake_fetch_entities), \
         patch("backfill_cache.api_get") as mock_api_get:
        mock_api_get.return_value = {"entities": {}}
        backfill_cache.backfill(field, family=False)

    # Q1 was applied from the cache branch, with the exact cached entity --
    # this is the "same function, same input" guarantee the plan relies on.
    q1_calls = [c for c in applied if c[0] == "Q1"]
    assert len(q1_calls) == 1
    assert q1_calls[0][1] is FIXTURE_ENTITY
    assert q1_calls[0][2] is False  # family

    # Q1's qid must never appear in any live api_get() call.
    assert "Q1" not in _requested_ids(mock_api_get)
    # Q2 (uncached) must have gone through the live path as always.
    assert "Q2" in _requested_ids(mock_api_get)


@pytest.mark.parametrize("field", ["dates", "sitelinks", "attributes", "relationships"])
def test_nothing_cached_matches_todays_behavior(cache_file, field, monkeypatch):
    """When wikidata_entities has nothing for anyone in this run (e.g. the
    DB is unreachable -- fetch_entities returns {} per its own documented
    failure contract), every composer must fall through to the live path
    exactly as it did before this change -- nobody gets silently skipped."""
    with patch("backfill_cache.wikidata_entities_store.fetch_entities", return_value={}), \
         patch("backfill_cache.api_get") as mock_api_get:
        mock_api_get.return_value = {"entities": {}}
        backfill_cache.backfill(field, family=False)

    assert _requested_ids(mock_api_get) == {"Q1", "Q2"}

-- Schema for the separate "wikidata_entities" database (not the main
-- "composers" app database -- connect with -d wikidata_entities).
--
-- Stores the full raw Wikidata entity (labels/claims/sitelinks) per QID,
-- as returned by get_entity() in fetch_wikidata_relationships.py, so
-- future extraction needs (e.g. calendarmodel) don't require re-fetching
-- composers already seen once. This is purely supplementary to the
-- existing wikidata_relationships.json cache, which keeps holding the
-- simplified/extracted fields every loader already reads.
--
-- Deliberately CREATE TABLE IF NOT EXISTS, NOT DROP TABLE IF EXISTS like
-- schema.sql's usual wipe-and-recreate convention: rebuilding this table
-- means re-fetching every composer from Wikidata's live API under rate
-- limits, not a cheap rerun. Never add a DROP TABLE here without a very
-- good reason.

CREATE TABLE IF NOT EXISTS entities (
    qid        TEXT PRIMARY KEY,
    entity     JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

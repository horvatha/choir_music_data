-- One-off migration: add is_citizenship/is_ethnicity to composer_nationalities
-- (see schema.sql for the full comments). Applied 2026-08-30.
--
-- Every existing row is set is_citizenship=TRUE, is_ethnicity=FALSE as a
-- starting point for manual review -- not a claim that every row really
-- is citizenship-only, just the least-disruptive default (matches how
-- every row was already being treated before these columns existed) for
-- hand-curation to correct row by row afterward.

ALTER TABLE composer_nationalities
    ADD COLUMN is_citizenship BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN is_ethnicity   BOOLEAN NOT NULL DEFAULT FALSE;

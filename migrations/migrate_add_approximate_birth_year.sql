-- One-off migration: add composers.approximate_birth_year, a single
-- sortable year for ORDER BY / display, regenerated from scratch by
-- backfill_approximate_birth_year.py. See schema.sql's CREATE TABLE
-- composers comment for the full rationale. Applied 2026-09-13.
ALTER TABLE composers ADD COLUMN approximate_birth_year INTEGER;

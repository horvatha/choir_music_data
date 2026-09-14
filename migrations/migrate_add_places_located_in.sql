-- One-off migration: add places.located_in_place_id, a display-only
-- "physically located inside this settlement" relationship for
-- non-administrative landmarks (streets, buildings), distinct from
-- parent_place_id's administrative-subdivision meaning. See schema.sql's
-- CREATE TABLE places comment for the full rationale. Applied 2026-08-23.
ALTER TABLE places ADD COLUMN located_in_place_id INTEGER REFERENCES places(id);

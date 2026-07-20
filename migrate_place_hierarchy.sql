-- One-time addition: places.place_type (Wikidata P31 label, e.g. "city",
-- "district of Budapest") and places.parent_place_id (current
-- administrative parent, Wikidata P131 -- e.g. a Budapest district's own
-- parent is Budapest). See the place_type/parent_place_id comment above
-- CREATE TABLE places in schema.sql for why this is distinct from
-- place_predecessors.

BEGIN;

ALTER TABLE places ADD COLUMN place_type TEXT;
ALTER TABLE places ADD COLUMN parent_place_id INTEGER REFERENCES places(id);

COMMIT;
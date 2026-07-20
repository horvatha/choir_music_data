-- One-time addition: place_predecessors, linking a place to an earlier,
-- now-absorbed place for composer-listing purposes only (not merged into
-- place_periods -- see the table comment in schema.sql for why Buda/Pest/
-- Óbuda -> Budapest needed this instead of the place_periods-merge
-- approach that already handles Königsberg -> Kaliningrad).

BEGIN;

CREATE TABLE place_predecessors (
    place_id             INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    predecessor_place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    display_order        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (place_id, predecessor_place_id)
);

COMMIT;
-- One-time migration: places.country_id stored a single static country per
-- place, so a composer's birth/death location always showed whatever one
-- country got picked regardless of which century they lived in (e.g.
-- Moscow always showed "Duchy of Moscow"). Restructures a single `places`
-- table (one row per Wikidata QID) into three: `places` (one row per
-- real-world place, e.g. Leningrad/St. Petersburg or Königsberg/
-- Kaliningrad collapse to one row), `place_qids` (every Wikidata item that
-- is/was that place, with an optional predecessor link for successions
-- like Königsberg -> Kaliningrad), and `place_periods` (the actual
-- (name, country, start_year, end_year) time windows, merged from every
-- constituent QID's own Wikidata claims). composers.birth_place_id/
-- death_place_id now reference place_periods directly, pre-resolved to
-- whichever window covers that composer's birth/death year.
--
-- Deliberately NOT run via schema.sql's drop-and-recreate-everything --
-- that drops `composers` itself, which would erase hand-verified merge/
-- classification work that only exists in DB state, not in the source
-- CSVs. This migration only touches place-related tables and the two
-- composer FK columns; rerun fetch_place_history.py + load_place_history.py
-- afterward to repopulate them (also rerun load_place_names.py /
-- load_us_states.py, which key off the columns being moved here).

BEGIN;

-- Detach composers from places -- birth/death place will be re-resolved to
-- place_periods rows once the new fetch/load scripts run.
ALTER TABLE composers DROP CONSTRAINT composers_birth_place_id_fkey;
ALTER TABLE composers DROP CONSTRAINT composers_death_place_id_fkey;
UPDATE composers SET birth_place_id = NULL, death_place_id = NULL;

-- Existing places rows are one-per-QID; being regrouped into one row per
-- real-world place, so old ids don't carry over. Cascades into place_names.
TRUNCATE place_names, places RESTART IDENTITY CASCADE;

ALTER TABLE places DROP COLUMN wikidata_id;
ALTER TABLE places DROP COLUMN country_id;
ALTER TABLE places DROP COLUMN country_code;

CREATE TABLE place_qids (
    id                       SERIAL PRIMARY KEY,
    place_id                 INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    wikidata_id              TEXT UNIQUE NOT NULL,
    predecessor_place_qid_id INTEGER REFERENCES place_qids(id)
);

CREATE TABLE place_periods (
    id           SERIAL PRIMARY KEY,
    place_id     INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    country_id   INTEGER REFERENCES countries(id),
    country_code TEXT,
    start_year   INTEGER,
    end_year     INTEGER
);

ALTER TABLE composers
    ADD CONSTRAINT composers_birth_place_id_fkey FOREIGN KEY (birth_place_id) REFERENCES place_periods(id),
    ADD CONSTRAINT composers_death_place_id_fkey FOREIGN KEY (death_place_id) REFERENCES place_periods(id);

COMMIT;

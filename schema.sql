DROP TABLE IF EXISTS images_composers;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS work_names;
DROP TABLE IF EXISTS works;
DROP TABLE IF EXISTS composer_relations;
DROP TABLE IF EXISTS instrument_references;
DROP TABLE IF EXISTS composer_instruments;
DROP TABLE IF EXISTS instruments;
DROP TABLE IF EXISTS composer_nationalities;
DROP TABLE IF EXISTS nationalities;
DROP TABLE IF EXISTS other_webpages;
DROP TABLE IF EXISTS composer_alt_names;
DROP TABLE IF EXISTS composer_wikilinks;
DROP TABLE IF EXISTS composer_eras;
DROP TABLE IF EXISTS composers;
DROP TABLE IF EXISTS place_periods;
DROP TABLE IF EXISTS place_names;
DROP TABLE IF EXISTS place_qids;
DROP TABLE IF EXISTS places;
DROP TABLE IF EXISTS states;
DROP TABLE IF EXISTS country_names;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS eras;
DROP TYPE IF EXISTS date_precision;

-- Lets name search be accent-insensitive: unaccent('Kodály') = 'Kodaly'.
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TYPE date_precision AS ENUM ('exact', 'circa', 'before', 'after', 'range', 'unknown');

CREATE TABLE eras (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- abbr is the standard ISO 3166-1 alpha-2 code (Wikidata P297), when the
-- country has one -- present for modern countries, null for historical/
-- non-standard entities (e.g. Austria-Hungary, Flanders) that only have a
-- wikidata_id to identify them. name/wikidata_id are always populated.
CREATE TABLE countries (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    abbr        TEXT,
    wikidata_id TEXT UNIQUE
);

-- A country's name in another language, e.g. hu: "Csehország" for the
-- "Czech Republic" row -- same (id, language, name) shape as
-- composer_alt_names, not a name_hu column, so adding more languages
-- later is just more rows, no schema change.
CREATE TABLE country_names (
    country_id INTEGER NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    language   TEXT NOT NULL,
    name       TEXT NOT NULL,
    PRIMARY KEY (country_id, language)
);

-- A first-level administrative division (currently U.S. states only, see
-- fetch_us_states.py) -- country_id keeps this extensible to other
-- countries' equivalents later without a schema change, same reasoning as
-- places.country_id below.
CREATE TABLE states (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    wikidata_id TEXT UNIQUE,
    country_id  INTEGER REFERENCES countries(id)
);

-- A real-world place, independent of however many Wikidata items or names
-- it's had over its history (e.g. Moscow's single Wikidata item under one
-- name throughout, or Leningrad/St. Petersburg's single item under four
-- different official names, or Königsberg/Kaliningrad's two separate,
-- Wikidata-linked items -- see place_qids/place_periods below). name is
-- the current/display name. latitude/longitude are nullable since not
-- every place entity on Wikidata carries a P625 coordinate claim, even
-- though most populated places do. state_id is U.S.-only for now (see
-- fetch_us_states.py) -- most other countries don't have same-named-place
-- ambiguity severe enough to be worth the extra fetch, so it's null
-- everywhere else rather than attempted for all.
-- place_type is Wikidata's own P31 (instance of) English label for the
-- place (e.g. "city", "district of Budapest", "village") -- descriptive
-- only, not a controlled vocabulary, so it varies in specificity/wording
-- across different kinds of places. parent_place_id is the place this one
-- is CURRENTLY administratively part of (Wikidata P131), e.g. a Budapest
-- district -> Budapest -- distinct from place_predecessors, which is a
-- historical "used to be its own separate place" link (Buda -> Budapest).
-- A place is never both: Wikidata's P131 for a genuine historical
-- predecessor is unreliable (verified: Buda's own P131 claim happens to
-- point at Budapest too, Pest's and Óbuda's don't, at some other
-- administrative entity we don't track as a place at all) and the
-- predecessor/successor relationship is what place_predecessors already
-- captures deliberately by hand -- so parent_place_id is left null for
-- any place already listed as somebody's place_predecessors row.
CREATE TABLE places (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    state_id        INTEGER REFERENCES states(id),
    place_type      TEXT,
    parent_place_id INTEGER REFERENCES places(id)
);

-- Every distinct Wikidata item that is or was this place. Most places have
-- exactly one row here; a place whose Wikidata history is split across
-- multiple items (e.g. Königsberg Q4120832 / Kaliningrad Q1829, linked by
-- Wikidata's P1365/P1366 "replaces"/"replaced by") has one row per item,
-- all sharing the same place_id. predecessor_place_qid_id records that
-- P1365 link directly (nullable -- most places have no predecessor).
CREATE TABLE place_qids (
    id                       SERIAL PRIMARY KEY,
    place_id                 INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    wikidata_id              TEXT UNIQUE NOT NULL,
    predecessor_place_qid_id INTEGER REFERENCES place_qids(id)
);

-- A time window during which a place had a specific name and belonged to a
-- specific country -- e.g. (Ленинград, Soviet Union, 1924-1991) for
-- Leningrad/St. Petersburg, or (Moscow, Tsardom of Russia, 1547-1721) for
-- Moscow. Windows are derived from every constituent place_qids row's own
-- Wikidata claims (P17 country claims and, when present, P1448 official-
-- name claims, both qualified by start/end time), merged onto one
-- timeline per place. start_year/end_year NULL means open-ended (earliest
-- known / still current respectively). country_code is a denormalized
-- copy of that window's country's standard abbreviation, same reasoning
-- as the old places.country_code -- null when the country has none of its
-- own (e.g. historical Flanders). composers.birth_place_id/death_place_id
-- reference a specific row here (not places directly), pre-resolved to
-- whichever window covers that composer's birth/death year, so the app
-- never has to do date-range logic at read time. default_language is a
-- two-letter code (e.g. 'ru', 'de') for whichever language `name` is
-- actually written in -- derived from the window's own country's official
-- language (Wikidata P37), not guessed from the text itself, so e.g.
-- Kaliningrad's Soviet-era windows resolve to 'ru' and Königsberg's
-- Prussian/German-era windows resolve to 'de'. Null when the country's
-- P37 doesn't map to a language this repo tracks (see LANGUAGE_QID_TO_CODE
-- in fetch_place_history.py) -- callers should treat that the same as an
-- unknown/untranslatable name, not assume any particular language.
CREATE TABLE place_periods (
    id               SERIAL PRIMARY KEY,
    place_id         INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    default_language TEXT,
    country_id       INTEGER REFERENCES countries(id),
    country_code     TEXT,
    start_year       INTEGER,
    end_year         INTEGER
);

-- A place's name in another language, e.g. hu: "Bécs" for the "Vienna"
-- row -- same (id, language, name) shape as composer_alt_names. Keyed to
-- the canonical place, not a specific historical window.
CREATE TABLE place_names (
    place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (place_id, language)
);

-- Links a place to an earlier, now-absorbed place -- for composer
-- listings only (e.g. showing Buda/Pest/Óbuda-born composers together
-- with Budapest's), not merged into place_periods. Distinct from
-- place_qids' predecessor_place_qid_id chain (same real-world place,
-- different Wikidata item, e.g. Königsberg/Kaliningrad): this is for a
-- genuine multiple-places-merged-into-one-new-place case (Buda + Pest +
-- Óbuda unified into Budapest in 1873), where each predecessor keeps its
-- own places/place_periods rows rather than being folded into one
-- timeline -- their own Wikidata items carry country claims that overlap
-- messily with the successor's own claims once merged (verified: Buda's
-- and Pest's own P17 claims each include an open-ended modern claim that
-- breaks place_periods' window-merging algorithm if attempted). A place
-- can have several predecessors (this is why it isn't just a self-FK on
-- places); display_order controls listing order since it isn't always
-- meaningfully chronological (e.g. Buda/Pest/Óbuda were all absorbed at
-- once).
CREATE TABLE place_predecessors (
    place_id             INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    predecessor_place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    display_order        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (place_id, predecessor_place_id)
);

CREATE TABLE composers (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    nationality       TEXT,
    wikidata_id       TEXT,

    birth_raw         TEXT,
    birth_year        INTEGER,
    birth_year_upper  INTEGER,
    birth_precision   date_precision,
    -- Exact calendar date, set only when Wikidata's P569 claim has
    -- day-level precision (its time values carry their own precision flag,
    -- e.g. year-only vs year+month vs full date) -- birth_year above stays
    -- the source of truth for "what year", this is purely an enrichment.
    birth_date        DATE,
    -- References a place_periods row, not places directly -- already
    -- resolved to whichever historical window covers this composer's
    -- birth year (see place_periods above). ON DELETE SET NULL (not the
    -- default RESTRICT) so load_birth_death_places.py can rerun: it
    -- deletes and re-inserts a place's period rows from scratch on every
    -- run, which would otherwise fail with a FK violation once composers
    -- start pointing at them -- the nulled-out FK gets re-resolved to a
    -- freshly-inserted period row later in that same script run.
    birth_place_id    INTEGER REFERENCES place_periods(id) ON DELETE SET NULL,

    death_raw         TEXT,
    death_year        INTEGER,
    death_year_upper  INTEGER,
    death_precision   date_precision,
    death_date        DATE,
    death_place_id    INTEGER REFERENCES place_periods(id) ON DELETE SET NULL,

    flourish_raw      TEXT,
    flourish_start    INTEGER,
    flourish_end      INTEGER,

    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE composer_eras (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    era_id      INTEGER NOT NULL REFERENCES eras(id) ON DELETE CASCADE,
    PRIMARY KEY (composer_id, era_id)
);

-- A composer's Wikipedia presence: one row per language edition they have a
-- page on. `language` is the two-letter subdomain WP uses (e.g. 'en', 'da',
-- 'de' for en.wikipedia.org, da.wikipedia.org, de.wikipedia.org). Composers
-- who only exist on a non-English Wikipedia simply have no 'en' row here;
-- composers with no Wikipedia page at all have no rows here.
CREATE TABLE composer_wikilinks (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    language    TEXT NOT NULL,
    title       TEXT NOT NULL,
    PRIMARY KEY (composer_id, language)
);

-- Some era CSVs store the plain display name in `title` instead of a real
-- Wikipedia slug (e.g. "Jean Sibelius" vs "Jean_Sibelius"), so uniqueness is
-- normalized (underscores -> spaces, case-folded) rather than exact-match.
CREATE UNIQUE INDEX composer_wikilinks_lang_title_norm_uidx
    ON composer_wikilinks (language, lower(regexp_replace(title, '_', ' ', 'g')));

-- A composer's name as spelled/known in another language or script, e.g.
-- Ernő Dohnányi's Hungarian name alongside the canonical "Ernst von
-- Dohnányi" in `composers.name`, or a Russian composer's Cyrillic name
-- alongside its Hungarian or English transliteration. Unlike wikilinks,
-- names aren't unique across composers (two different people can share a
-- spelling), so there's no cross-composer uniqueness constraint.
CREATE TABLE composer_alt_names (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    language    TEXT NOT NULL,
    name        TEXT NOT NULL,
    PRIMARY KEY (composer_id, language)
);

-- A composer's page on some other (non-Wikipedia) biographical site, e.g.
-- the Liszt Academy's "Nagy elodok" lexicon (source = 'lfze_nagy_elodok').
-- Structured like composer_wikilinks (one row per composer per source, no
-- N:M) rather than composer_alt_names, since these are specific pages/URLs,
-- not alternate name spellings. author is plain text, not a FK -- most
-- authors of these articles aren't composers already in this DB; a nullable
-- author_id FK can be added later for the ones who are.
CREATE TABLE other_webpages (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    url         TEXT NOT NULL,
    language    TEXT NOT NULL,
    title       TEXT,
    author      TEXT,
    fetched_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (composer_id, source)
);

-- composers.nationality stays as the raw source text (like birth_raw /
-- death_raw) -- it's inconsistent enough (375+ distinct strings: plain
-- "German", compounds like "German-born Canadian", garbled ones like
-- "Western Europeanprobably French or German") that parsing it into this
-- N:M table is a lossy best-effort, not a replacement.
CREATE TABLE nationalities (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- is_origin_only is TRUE when the source text explicitly said a composer
-- was born under this nationality but became active as a composer under
-- the other one (e.g. "German-born Canadian" -> German=TRUE, Canadian=
-- FALSE). It is NOT a general "were they born here" fact: a composer with
-- a single plain nationality (e.g. Berkesi Sándor, "Hungarian") gets FALSE,
-- since there's no other nationality they were active under instead.
-- Plain compounds with no "-born" marker (e.g. "Greek-American") also get
-- FALSE on both sides -- the source doesn't say which came first.
CREATE TABLE composer_nationalities (
    composer_id     INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    nationality_id  INTEGER NOT NULL REFERENCES nationalities(id) ON DELETE CASCADE,
    is_origin_only  BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (composer_id, nationality_id)
);

-- Image files themselves live on disk (composer_images/<filename>, thumbnail
-- at composer_images/thumbs/<filename stem>_thumb.<ext>), not as bytes in
-- Postgres -- this table is just the metadata + composer association.
CREATE TABLE images (
    image_id  SERIAL PRIMARY KEY,
    filename  TEXT NOT NULL,
    x         INTEGER NOT NULL,
    y         INTEGER NOT NULL,
    thumbx    INTEGER NOT NULL,
    thumby    INTEGER NOT NULL,
    comment   TEXT,
    year      INTEGER
);

CREATE TABLE images_composers (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    image_id    INTEGER NOT NULL REFERENCES images(image_id) ON DELETE CASCADE,
    PRIMARY KEY (composer_id, image_id)
);

-- wikidata_id is nullable: instruments can be added by hand (or found via a
-- source with no Wikidata mapping) without a QID, unlike composers.wikidata_id
-- which every fetched composer has.
CREATE TABLE instruments (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    wikidata_id TEXT
);

CREATE TABLE composer_instruments (
    composer_id   INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    PRIMARY KEY (composer_id, instrument_id)
);

-- Supporting evidence for a composer_instruments fact that didn't come
-- from Wikidata's own P1303 claim (which needs no separate citation here --
-- the claim itself is the reference, on Wikidata). source is a machine key
-- like 'lfze_nagy_elodok' (see other_webpages.source); a composer/instrument
-- pair can have more than one reference, hence source is part of the key
-- rather than the table being 1:1 with composer_instruments.
CREATE TABLE instrument_references (
    composer_id   INTEGER NOT NULL,
    instrument_id INTEGER NOT NULL,
    source        TEXT NOT NULL,
    url           TEXT,
    evidence      TEXT,
    PRIMARY KEY (composer_id, instrument_id, source),
    FOREIGN KEY (composer_id, instrument_id)
        REFERENCES composer_instruments (composer_id, instrument_id) ON DELETE CASCADE
);

-- A composer-to-person relationship (currently from Wikidata's
-- RELATIONSHIP_PROPS in fetch_wikidata_relationships.py: father, mother,
-- student_of, notable_student, doctoral_advisor, influenced_by; other
-- sources like the lfze bios may add rows later). related_wikidata_id is
-- nullable -- a source like lfze won't always give a QID for the other
-- person, unlike Wikidata's own claims which always do. related_composer_id
-- is also nullable, and only set when the other person matches an existing
-- composers row (by wikidata_id when known), so the app can link to that
-- composer's own page when possible and fall back to plain text otherwise.
CREATE TABLE composer_relations (
    id                  SERIAL PRIMARY KEY,
    composer_id         INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    relation_type       TEXT NOT NULL,
    related_name        TEXT NOT NULL,
    related_wikidata_id TEXT,
    related_composer_id INTEGER REFERENCES composers(id) ON DELETE SET NULL,
    UNIQUE (composer_id, relation_type, related_wikidata_id)
);

-- A composer's work -- one row per work, not a junction table, since a
-- work has exactly one composer (unlike instruments, which are genuinely
-- many-to-many). wikidata_id is nullable like instruments.wikidata_id, for
-- the same reason: a work added later from a non-Wikidata source won't
-- always have a QID. wikidata_notable_work marks rows that came from
-- Wikidata's own P800 "notable work" claim specifically -- everything
-- loaded today is TRUE, but this lets a future, broader source (e.g. a
-- full works catalogue, not just Wikidata's curated "notable" subset)
-- add rows without them being mistaken for Wikidata-flagged notability.
CREATE TABLE works (
    id                    SERIAL PRIMARY KEY,
    composer_id           INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    wikidata_id           TEXT,
    wikidata_notable_work BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (composer_id, wikidata_id)
);

-- A work's title in another language, e.g. hu: "Ruszalka" for the
-- "Rusalka" row -- same (id, language, name) shape as composer_alt_names.
CREATE TABLE work_names (
    work_id  INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (work_id, language)
);

CREATE INDEX idx_composers_birth_year ON composers(birth_year);
CREATE INDEX idx_composer_eras_era ON composer_eras(era_id);
CREATE INDEX idx_composer_relations_related_composer ON composer_relations(related_composer_id);
CREATE INDEX idx_works_composer ON works(composer_id);
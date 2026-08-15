DROP TABLE IF EXISTS images_composers;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS work_genres;
DROP TABLE IF EXISTS genre_names;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS work_names;
DROP TABLE IF EXISTS works;
DROP TABLE IF EXISTS composer_relations;
DROP TABLE IF EXISTS instrument_references;
DROP TABLE IF EXISTS composer_instruments;
DROP TABLE IF EXISTS instrument_names;
DROP TABLE IF EXISTS instruments;
DROP TABLE IF EXISTS instrument_group_names;
DROP TABLE IF EXISTS instrument_groups;
DROP TABLE IF EXISTS composer_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS composer_nationalities;
DROP TABLE IF EXISTS nationality_names;
DROP TABLE IF EXISTS nationalities;
DROP TABLE IF EXISTS other_webpages;
DROP TABLE IF EXISTS composer_alt_names;
DROP TABLE IF EXISTS composer_wikilinks;
DROP TABLE IF EXISTS composer_eras;
DROP TABLE IF EXISTS composers;
DROP TABLE IF EXISTS place_periods;
DROP TABLE IF EXISTS place_names;
DROP TABLE IF EXISTS place_qids;
DROP TABLE IF EXISTS place_predecessors;
DROP TABLE IF EXISTS places;
DROP TABLE IF EXISTS states;
DROP TABLE IF EXISTS country_names;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS eras;
DROP TYPE IF EXISTS date_precision;
DROP TYPE IF EXISTS wikidata_calendar;

-- Lets name search be accent-insensitive: unaccent('Kodály') = 'Kodaly'.
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TYPE date_precision AS ENUM ('exact', 'circa', 'before', 'after', 'range', 'unknown');
-- Which calendar birth_date/death_date's day-precision Wikidata claim was
-- recorded in -- NULL when unknown/not applicable (e.g. no day-precision
-- claim at all). See fetch_wikidata_relationships.py's extract_dates() and
-- _CALENDAR_MODELS. Matters for pre-1918 Russia, pre-1752 England, pre-1700
-- Protestant Germany, etc., where a Julian-calendar date can differ from
-- its Gregorian form by 10-13 days -- never assume from nationality alone,
-- Wikidata doesn't always carry a Julian claim even for historically-Julian
-- people.
CREATE TYPE wikidata_calendar AS ENUM ('gregorian', 'julian');

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
    birth_calendar    wikidata_calendar,
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
    death_calendar    wikidata_calendar,
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

-- Translated forms of nationalities.name, same (entity_id, language, name)
-- shape as genre_names/instrument_names/work_names -- see
-- translate_nationalities.py for how it's populated (LLM-translated
-- directly, not sourced from Wikidata -- these are plain demonym
-- adjectives, not proper nouns, so there's no per-entity QID to fetch a
-- label from).
CREATE TABLE nationality_names (
    nationality_id INTEGER NOT NULL REFERENCES nationalities(id) ON DELETE CASCADE,
    language       TEXT NOT NULL,
    name           TEXT NOT NULL,
    PRIMARY KEY (nationality_id, language)
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
    -- TRUE when the row was assigned purely by trusting a Wikidata
    -- citizenship (P27) claim -> nationality mapping at face value (e.g.
    -- "citizenship: France" -> French), with no independent check of the
    -- composer's own Wikipedia article or another source -- see the
    -- nationality_citizenship_review.md "bulk assignment" pass. FALSE
    -- (default) means either it was cross-checked against a source, or it
    -- was never citizenship-derived at all (e.g. set by the original CSV
    -- load). Not itself a correctness signal -- a need_to_check=TRUE row
    -- may well be right, it just hasn't been verified beyond the raw claim.
    need_to_check   BOOLEAN NOT NULL DEFAULT FALSE,
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

-- An instrument's name in another language, e.g. hu: "hegedű" for the
-- "violin" row -- same (id, language, name) shape as place_names/
-- work_names/composer_alt_names, not a name_hu column, so adding more
-- languages later is just more rows, no schema change (see CLAUDE.md's
-- "Target languages for translated names"). Populated by
-- fetch_instrument_names.py / load_instrument_names.py from Wikidata
-- labels on instruments.wikidata_id; an instrument with no wikidata_id
-- (added by hand) simply has no rows here.
CREATE TABLE instrument_names (
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    language      TEXT NOT NULL,
    name          TEXT NOT NULL,
    PRIMARY KEY (instrument_id, language)
);

-- A small, hand-curated family/subfamily taxonomy (winds, strings,
-- percussion, keyboards, electronic, other; brass/woodwind under winds,
-- bowed/plucked under strings) -- deliberately NOT derived automatically
-- from Wikidata's subclass-of (P279) graph, which is inconsistently deep
-- across instruments (see load_instrument_groups.py's GROUPS constant and
-- its classify() docstring for why, and the actual per-instrument
-- assignment logic). parent_group_id is NULL for a top-level group; a
-- group with no parent and no children (e.g. "other", the catch-all for
-- instruments the classifier can't place) is valid and expected -- not
-- every instrument needs two levels. wikidata_id is nullable (the "other"
-- group has none) and UNIQUE like tags.wikidata_id, same reasoning: it's
-- the merge key, not name.
-- display_order is a small hand-assigned rank among siblings (other
-- top-level groups, or other subfamilies under the same parent) -- not
-- inferred from insertion order/id, so the display order stays correct
-- and self-documenting even if load_instrument_groups.py's GROUPS list
-- is later reordered or re-run out of order. "other" (the catch-all for
-- instruments the classifier can't place) is always last among top-level
-- groups.
CREATE TABLE instrument_groups (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    wikidata_id     TEXT UNIQUE,
    parent_group_id INTEGER REFERENCES instrument_groups(id),
    display_order   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE instrument_group_names (
    group_id INTEGER NOT NULL REFERENCES instrument_groups(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (group_id, language)
);

-- Added via ALTER (not inline on the instruments CREATE TABLE above) since
-- instrument_groups has to exist first. Each instrument gets at most one
-- group -- its most specific known one (a subfamily like "brass" when the
-- classifier could tell, else the top-level family, else NULL/"other").
ALTER TABLE instruments ADD COLUMN group_id INTEGER REFERENCES instrument_groups(id);

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

-- A loose stylistic/cultural tag a composer is associated with -- sourced
-- from Wikidata's P135 property, which Wikidata itself calls "movement"
-- (e.g. Impressionism, Serialism, Second Viennese School), but "movement"
-- overclaims what most of these actually are: Wikidata's own P31 typing of
-- the target items splits them into music genre, musical movement, art
-- movement, composition school, compositional technique, etc. -- e.g.
-- "Baroque music" is typed as a music genre, not a movement with anything
-- like a manifesto or a self-identified group behind it, unlike genuine
-- movements such as Futurism or Fluxus. Deliberately not subcategorized by
-- that typing here -- flat and unlabeled ("tags"), not exclusive/
-- hierarchical ("categories"): a composer can carry several overlapping
-- ones at once, and at ~80 distinct values the flat list is still
-- browsable as-is. Distinct from eras: eras is a small, curated, purely
-- chronological backbone (every composer gets 1+ bucket, hand-overridden
-- where ambiguous); a composer can have zero, one, or several tags, at a
-- much finer and less chronological granularity, sourced as-is from
-- Wikidata rather than curated. wikidata_id (not name) is the merge key
-- and is UNIQUE -- two distinct Wikidata items can carry the identical
-- English label (e.g. Q2426218 "modernism" = musical modernism, vs Q878985
-- "modernism" = the general cultural/art movement), so name alone can't be
-- trusted to identify a tag; NAME_OVERRIDES in load_tags.py renames the
-- former to "musical modernism" by hand to keep the two readable as
-- distinct rows, same pattern as this repo's other hand overrides
-- (ERA_OVERRIDES, MANUAL_PLACE_CLUSTERS). wikidata_id stays nullable so a
-- tag can still be added by hand with no QID.
CREATE TABLE tags (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    wikidata_id TEXT UNIQUE
);

COMMENT ON TABLE tags IS
    'Loose, flat, non-hierarchical stylistic/cultural tags for a composer. '
    'Sourced from Wikidata''s P135 property, which Wikidata calls "movement" '
    '-- renamed here since most values (e.g. Baroque music, typed by '
    'Wikidata itself as a music genre) are not movements in the sense of a '
    'self-identified group with a manifesto (contrast genuine cases like '
    'Futurism or Fluxus). See the source comment above this table for the '
    'full rationale.';

COMMENT ON COLUMN tags.wikidata_id IS
    'The Wikidata QID of the P135 ("movement") target item this tag was '
    'loaded from. Nullable so a tag can be added by hand with no QID. This '
    'is the merge key (not name) -- see load_tags.py.';

CREATE TABLE composer_tags (
    composer_id INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (composer_id, tag_id)
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
-- A musical genre/form (Wikidata P7937 "form of creative work", e.g.
-- "cantata", "mass", "concerto") -- same (id, name, wikidata_id) shape as
-- tags, kept as its own table rather than reusing tags since a genre and a
-- movement/tag (P135) are different concepts that happen to share a shape.
CREATE TABLE genres (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    wikidata_id TEXT UNIQUE
);

-- A genre's name in another language -- same (id, language, name) shape as
-- instrument_names/work_names.
CREATE TABLE genre_names (
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (genre_id, language)
);

CREATE TABLE works (
    id                    SERIAL PRIMARY KEY,
    composer_id           INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    wikidata_id           TEXT,
    wikidata_notable_work BOOLEAN NOT NULL DEFAULT FALSE,
    -- Three separate Wikidata date claims, each loaded only from
    -- year-level precision up -- century/decade-precision claims (e.g. "9th
    -- century") are left out rather than mapped onto a specific year. The
    -- *_year column is set whenever that claim exists at all; *_month/*_day
    -- are only set when Wikidata's claim carries that much precision, so a
    -- year-only date leaves both NULL. See load_work_dates.py.
    composed_year         INTEGER,  -- P571 "inception"
    composed_month        INTEGER,
    composed_day          INTEGER,
    premiered_year        INTEGER,  -- P1191 "date of first performance"
    premiered_month       INTEGER,
    premiered_day         INTEGER,
    published_year        INTEGER,  -- P577 "publication date"
    published_month       INTEGER,
    published_day         INTEGER,
    catalog_code          TEXT,  -- P528, e.g. "BWV 565", "K. 550"
    -- CPDL (Choral Public Domain Library) page slug, e.g.
    -- "Stabat_Mater_(Antonio_Vivaldi)" -- not a full URL, since the app
    -- builds https://www.cpdl.org/wiki/index.php/<slug> from it, same as
    -- wikidata_id not being a full Wikidata URL either.
    cpdl_id               TEXT,  -- P2000
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

-- A work can carry more than one genre (Wikidata P7937 is multi-valued for
-- ~8% of works, e.g. both "opera" and "tragedy") -- many-to-many, same
-- pattern as composer_tags/composer_instruments.
CREATE TABLE work_genres (
    work_id  INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (work_id, genre_id)
);

-- A work's instrumentation (Wikidata P870) -- reuses the composers'
-- instruments/instrument_names tables rather than a separate one, since
-- most instrument QIDs referenced here already exist there (e.g. "organ",
-- "violin") -- see load_work_instruments.py. Many-to-many since a work
-- typically names several instruments.
CREATE TABLE work_instruments (
    work_id       INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    PRIMARY KEY (work_id, instrument_id)
);

-- A musical key/tonality (Wikidata P826, e.g. "D minor") -- named
-- musical_keys (not "keys") to avoid reading like a schema pun next to
-- primary/foreign keys. Same (id, name, wikidata_id) + translation-table
-- shape as genres.
CREATE TABLE musical_keys (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    wikidata_id TEXT UNIQUE
);

CREATE TABLE musical_key_names (
    musical_key_id INTEGER NOT NULL REFERENCES musical_keys(id) ON DELETE CASCADE,
    language        TEXT NOT NULL,
    name            TEXT NOT NULL,
    PRIMARY KEY (musical_key_id, language)
);

-- A handful of works (4/106) carry more than one key claim (e.g. a piece
-- that modulates) -- many-to-many, same reasoning as work_genres.
CREATE TABLE work_musical_keys (
    work_id        INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    musical_key_id INTEGER NOT NULL REFERENCES musical_keys(id) ON DELETE CASCADE,
    PRIMARY KEY (work_id, musical_key_id)
);

CREATE INDEX idx_composers_birth_year ON composers(birth_year);
CREATE INDEX idx_composer_eras_era ON composer_eras(era_id);
CREATE INDEX idx_composer_relations_related_composer ON composer_relations(related_composer_id);
CREATE INDEX idx_works_composer ON works(composer_id);
CREATE INDEX idx_works_composed_year ON works(composed_year);
CREATE INDEX idx_work_genres_genre ON work_genres(genre_id);
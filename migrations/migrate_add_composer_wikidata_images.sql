-- One-off migration: add composer_wikidata_images (see schema.sql for the
-- full comment). Applied 2026-08-28.

CREATE TABLE composer_wikidata_images (
    id           SERIAL PRIMARY KEY,
    composer_id  INTEGER NOT NULL REFERENCES composers(id) ON DELETE CASCADE,
    full_url     TEXT NOT NULL,
    thumb_url    TEXT NOT NULL,
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX composer_wikidata_images_one_preferred
    ON composer_wikidata_images (composer_id) WHERE is_preferred;

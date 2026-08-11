# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A pipeline that collects composer biographical data (name, nationality, birth/death, Wikipedia links) from Wikipedia composer lists in multiple languages, cleans/dedupes it, and loads it into a Postgres database. The repo is the *source of truth for the DB schema* — a separate FastAPI app, `concert_music_app` (sibling repo at `/home/ha/repo/concert_music_app`), reads directly from the tables this repo creates. **Any schema change here must be checked against that repo's `src/concert_music_app/adapters/`, which query the tables by name** — it has no independent migration path and will break silently (e.g. `column does not exist`) if a column/table it relies on is renamed or moved. The dependency isn't just the DB: `concert_music_app` also reads image files from this repo's `composer_images/` directory (see "Composer pictures" below), mounted as a volume when it runs as a container.

The repo itself is a mix of the live pipeline (see below) and a long tail of one-off/exploratory scripts and data files from earlier iterations (multiple `composers_*_.csv`/`_old.csv`/`_orig.wiki` variants, notebooks, `Wikipedia-XMLs/`). When in doubt about whether a script is part of the current pipeline, check whether it's referenced from another still-used script — most of the loose top-level files are dead ends kept for reference, not code paths anything depends on.

## Database

Postgres runs in a podman container (not a system service):

```bash
podman run -d --name composers-pg \
  -e POSTGRES_PASSWORD=composers_dev -e POSTGRES_DB=composers -e POSTGRES_USER=composers \
  -p 5432:5432 -v composers-pg-data:/var/lib/postgresql/data \
  docker.io/library/postgres:17
```

(command also saved in `podman_cmds/psql.txt`). Connection is always via standard libpq env vars — `PGHOST=localhost PGPORT=5432 PGDATABASE=composers PGUSER=composers PGPASSWORD=composers_dev` — never hardcoded in scripts. Apply/reset the schema with:

```bash
cat schema.sql | podman exec -i composers-pg psql -U composers -d composers
```

`schema.sql` starts with `DROP TABLE IF EXISTS ...` — running it wipes and recreates every table. This is the intended workflow for schema changes in this project (rerun the loaders after) rather than hand-written migrations; the `migrate_*.sql` files at the root are one-off historical migrations already applied, not a live migration chain.

### Schema shape

- `composers` — one row per person. No `article` column (moved out, see below).
- `eras` / `composer_eras` — many-to-many; a composer can span multiple eras (e.g. late Romantic into 20th-century).
- `composer_wikilinks(composer_id, language, title)` — a composer's Wikipedia page per language edition (`language` is the two-letter WP subdomain: `en`, `hu`, ...). PK is `(composer_id, language)` — one page per language per composer. A composer with no rows here has no known Wikipedia article.
- `composer_alt_names(composer_id, language, name)` — a composer's name as spelled in another language/script (e.g. a Hungarian composer's Hungarian name alongside the canonical name in `composers.name`), distinct from wikilinks (a name isn't a unique key the way a wiki title is — two different composers can share a spelling).

`composers.name` is meant to hold the international/canonical form; same-person duplicates that entered via different-language source lists (different spelling, so they don't merge automatically on load) get resolved by hand with `merge_composers.py`, which folds one row into another and records the dropped name as an alt name.

### Target languages for translated names

Domain-data translations (instrument names, work titles, place names, etc. -- not static UI copy, which is `concert_music_app`'s gettext/.po files) always use an extensible `(entity_id, language, name)` table, e.g. `instrument_names`, `place_names`, `work_names`, `composer_alt_names` -- never a `name_hu`-style column. When fetching a new batch of these from Wikidata (see `python3 cli.py fetch labels --entity instrument` for the pattern), the target language list is:

`hu, es, fr, en, de, cs, uk, it, hr, pl, ru, nl` (Hungarian, Spanish, French, English, German, Czech, Ukrainian, Italian, Croatian, Polish, Russian, Dutch)

English is fetched too but only kept when it differs from whatever the row's existing base/default name already is (see `python3 cli.py load names --entity instrument`) -- avoids a redundant duplicate row for the common case where the base name already came from Wikidata's English label. `fetch_wikidata_relationships.py`'s `TARGET_LANGUAGES` is the single source of truth for this list; keep it and this section in sync if it changes.

### Composer pictures

`images(image_id, filename, x, y, thumbx, thumby, comment, year)` +
`images_composers(composer_id, image_id)` (N:M) store picture *metadata*
only — the actual files live on disk in `composer_images/` (originals) and
`composer_images/thumbs/` (`<stem>_thumb.<ext>`, auto-generated at the
largest size that fits inside 500x500, hard-linked to the original instead
of duplicated when the original already fits), not as bytes in Postgres.
There is no loader script in this repo — `concert_music_app` serves and
accepts uploads for these files over HTTP (its upload form is the only way
new pictures get added), reading/writing the `composer_images/` directory
directly.

## The live pipeline

1. **Source → CSV**: Each era/language has its own CSV (`composers_Medieval.csv`, `composers_Baroque.csv`, ..., `composers_Hungarian.csv`), columns `article,name,birth,death,nationality[,era]`. `parse_hu_wiki_composers.py` is the pattern for turning a raw Wikipedia list wikitext dump (e.g. `zeneszerzok_hu_wiki.txt`) into one of these CSVs — bullet-list wikilinks (`*[[Article|Display]] (birth – death)`) parsed into rows, with hand-maintained `ERA_OVERRIDES` for composers whose era isn't derivable from the source list itself.
2. **CSV → DB**: `load_composers.py` loads the English-language era CSVs (`SOURCES` dict), merging a composer onto an existing row by their normalized `en` wikilink title (falling back to exact name match for composers with no Wikipedia page), so rerunning it is idempotent. `load_hungarian_composers.py` does the equivalent for `composers_Hungarian.csv`, but merges by (birth year, death year, name-as-a-set-of-words) instead — this catches same-alphabet reordering (Hungarian "Ligeti György" ↔ existing "György Ligeti") but *not* translated or transliterated names, which land as new rows.
3. **Dedup**: `find_duplicate_composers.py` reports composers sharing an exact birth+death year (narrowed to groups touching a non-`en` wikilink, otherwise too noisy — most collisions among the thousands of other composers are coincidental). This is the tool for finding same-person-different-spelling duplicates (translated names, Russian transliterations, etc.) that the loaders' automatic matching misses. Nothing here is auto-merged — `merge_composers.py <keep_id> <drop_id> <language>` does the actual merge once you've confirmed a pair by hand.
4. **Classification**: `classify_hu_wiki_composers.py` flags Hungarian-list composers who are pop/rock/light-music figures rather than concert-music composers, using hu.wikipedia.org category membership via the MediaWiki API (cached in `hu_wiki_categories_cache.json`). It's a heuristic (category keyword match, e.g. `Kategória:Magyar könnyűzenei előadók`), not authoritative — writes `flag`/`flag_reason` columns back onto `composers_Hungarian.csv` rather than deleting anything, so wrong flags get fixed by hand later. `load_hungarian_composers.py` skips rows with `flag == 'pop'`.

Running the whole pipeline from scratch: apply `schema.sql`, then `python3 load_composers.py`, then `python3 load_hungarian_composers.py`.

## Tests

`test.py` and `test_investigate_wikipedia_pages.py` use pytest, but pytest is **not currently installed** in `.venv` — install it first (`pip install pytest`) before trying to run them.
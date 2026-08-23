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

### Syncing local dev data to the production server

Local dev (this podman DB) and the production server's DB (`pyedu.hu`, native Postgres install — see its own CLAUDE.md/memory for topology) are **independent databases that drift apart** as pipeline scripts get rerun locally. There's no live replication; syncing is a manual, one-shot dump/restore:

```bash
./backup_database.sh
```

This dumps the local DB, then automatically `scp`s it to `pyedu.hu:~/` and prints the exact restore command. The upload is automatic (safe — just copies a file); the restore is deliberately **not** automated, since it's destructive to the production DB (`pg_restore --clean --if-exists`, drops and recreates everything). Run it yourself:

```bash
ssh pyedu.hu
bash restore_database.sh ~/composers_backup_<timestamp>.dump
```

Note `restore_database.sh` isn't on the server's non-interactive `PATH` (only `/usr/local/bin:/usr/bin:/bin:/usr/games`) — from a plain `ssh host command` invocation (not an interactive login shell) it must be run as `bash restore_database.sh ...` or with an explicit path, not as a bare command, even though it works bare in an interactive shell sitting in `$HOME`.

Before syncing, it's worth checking whether local dev itself has an unapplied backlog first — rerunning a loader like `load_composer_alt_names.py` or `load_birth_death_places.py` can surface a large batch of names/places that were fetched into the Wikidata cache but never actually loaded into Postgres (these loaders are idempotent and safe to rerun anytime; `load_birth_death_places.py`'s own output tells you if `fetch_place_history.py` needs a rerun first, via its "N places skipped" count).

### Testing DB changes safely

Local dev is not a throwaway sandbox — it accumulates real hand-curated
state (manual composer merges/deletes, `MANUAL_COMPOSER_TAGS`-style
overrides, nationality/place fixes) that isn't all reconstructable just by
rerunning loaders from source. Before rerunning a script whose correctness
you're not already confident of — a script with a new/changed code path,
or a `TRUNCATE`-based loader you haven't rerun recently — take a **local**
safety snapshot first, skipping the production upload:

```bash
./backup_database.sh --no-copy
```

This is fast (a local `pg_dump`, no `scp`) — cheap enough to run before any
rerun you're even slightly unsure about, not just big destructive ones.

**Verifying "did we actually reach the same state" — don't just eyeball
row counts on the live DB.** Restore the snapshot into a disposable
scratch container (never overwrite the real `composers-pg`) and diff
against it directly:

```bash
podman run -d --name composers-pg-verify \
  -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=composers_scratch -e POSTGRES_USER=composers \
  docker.io/library/postgres:17
sleep 3
podman cp pg_dumps/composers_backup_<timestamp>.dump composers-pg-verify:/tmp/backup.dump
podman exec -i composers-pg-verify pg_restore -U composers -d composers_scratch --no-owner --no-privileges /tmp/backup.dump

# compare row counts per table, then diff actual rows for anything that differs
for tbl in composers composer_wikilinks composer_alt_names nationalities composer_nationalities tags composer_tags; do
  b=$(podman exec -i composers-pg-verify psql -U composers -d composers_scratch -At -c "SELECT count(*) FROM $tbl;")
  l=$(podman exec -i composers-pg psql -U composers -d composers -At -c "SELECT count(*) FROM $tbl;")
  echo "$tbl: backup=$b live=$l"
done

# once done:
podman stop composers-pg-verify && podman rm composers-pg-verify
```

A row-count match isn't proof by itself — diff the actual rows for any
table that differs (e.g. `SELECT c.name, t.name FROM composer_tags ct JOIN
composers c ... JOIN tags t ...` on both sides, `diff` the sorted output)
to confirm every difference is one you actually intended, not a stray
side effect. This exact workflow caught a real bug on 2026-08-23:
rerunning `load_composers.py` to verify an unrelated CSV path change
silently inserted 73 duplicate composer rows via a false-positive in its
`looks_like_different_person` name-collision heuristic — invisible from
the loader's own success output, only found by diffing against a backup
taken minutes earlier.

Row-count matching only works if nothing legitimate changed between the
backup and the state you're checking — if real work happened in between
(e.g. an intentional tag backfill), diff the specific rows affected by
that work separately and confirm they, and only they, account for the
difference (as opposed to assuming any list of unequal counts must be
your bug).

### Schema shape

- `composers` — one row per person. No `article` column (moved out, see below).
- `eras` / `composer_eras` — many-to-many; a composer can span multiple eras (e.g. late Romantic into 20th-century).
- `composer_wikilinks(composer_id, language, title)` — a composer's Wikipedia page per language edition (`language` is the two-letter WP subdomain: `en`, `hu`, ...). PK is `(composer_id, language)` — one page per language per composer. A composer with no rows here has no known Wikipedia article.
- `composer_alt_names(composer_id, language, name)` — a composer's name as spelled in another language/script (e.g. a Hungarian composer's Hungarian name alongside the canonical name in `composers.name`), distinct from wikilinks (a name isn't a unique key the way a wiki title is — two different composers can share a spelling).
- `nationalities` / `composer_nationalities(composer_id, nationality_id, is_origin_only, need_to_check)` — many-to-many; a composer can carry several nationality tags. `is_origin_only` marks a nationality the composer was *born* under but isn't identified with professionally/civically (e.g. Walter Gieseking born in Lyon but German; Stravinsky's Russian nationality is origin-only once French/American are added — see below). `need_to_check` flags a tag that was inferred rather than independently confirmed (citizenship-only inference from a Wikidata P27 claim with no corroborating Wikipedia prose, or a birthplace-only guess with no citizenship claim at all, or a source that hedged with a literal "?"). `composers.nationality` is a flat, human-readable text column used for list-view display and must be kept in sync with the structured table by hand — a mismatch (flat text says one thing, the structured tag says another) is a bug to fix, not two independent facts.

`composers.name` is meant to hold the international/canonical form; same-person duplicates that entered via different-language source lists (different spelling, so they don't merge automatically on load) get resolved by hand with `merge_composers.py`, which folds one row into another and records the dropped name as an alt name.

### Nationality vs. ethnicity vs. citizenship

`composer_nationalities` conflates three genuinely different concepts, because the source material (Wikidata, Wikipedia prose, old CSV nationality columns) does too:

- **Citizenship** is a real, verifiable legal status (naturalization, a passport) — reliable for modern composers, but anachronistic before the nation-state era; there was no bureaucratic "citizenship" for most of European history (subjecthood to a local lord/prince/monarch, not a tracked legal status, and often no formal mechanism to even lose an earlier one after later naturalizing elsewhere). Wikidata's P27 ("country of citizenship") is applied elastically to pre-modern people — it's a general-purpose biographical field inherited from library/archival authority-control conventions (VIAF-style), not a precise legal claim for historical figures. Treat P27 with more skepticism the further back the composer lived; for medieval subjects it usually just means "the polity/region conventionally associated with them."
- **Ethnicity** is ancestral/cultural origin, independent of citizenship, and normally singular even when nationality is plural or changes over a lifetime (Stravinsky: Russian ethnicity throughout, but Russian-Empire-subject → French-naturalized → American-naturalized nationality in sequence).
- Only split a tag into separate ethnicity + nationality rows when there's a real, sourced reason the distinction matters to how the person is actually described (e.g. Kosovar + Albanian, given Kosovo's specific ethnic history) — don't invent an ethnicity split as a default policy. Switzerland's German/French/Italian-speaking regions do **not** get one; there's no "Swiss German" ethnicity claim being made about a Zürich-born composer, just a language region within one civic nationality.
- A **real compound term naming an actual historical/musicological school or group** (e.g. "Franco-Flemish") should be kept whole, not split into its component words — check whether it's a genuine term of art (a real "school") before splitting anything.
- **Genuine either/or ambiguity in a source** (e.g. a CSV nationality field literally reading "French or Flemish") should be resolved by splitting into two separate tags with `need_to_check = TRUE` on both — that's different from the compound-term case above, since there's no single named "French or Flemish" school being referred to.
- A **literal "?" in source nationality text** is a genuine uncertainty marker — `load_nationalities.py`'s `_clean()` strips a trailing "?" when parsing free text into a tag, so check for it and propagate the uncertainty into `need_to_check = TRUE` on the resulting tag rather than silently dropping it (a full-DB check is `SELECT ... FROM composers WHERE nationality ~ '\?'` before any bulk nationality load/cleanup).

### Target languages for translated names

Domain-data translations (instrument names, work titles, place names, etc. -- not static UI copy, which is `concert_music_app`'s gettext/.po files) always use an extensible `(entity_id, language, name)` table, e.g. `instrument_names`, `place_names`, `work_names`, `composer_alt_names` -- never a `name_hu`-style column. When fetching a new batch of these from Wikidata (see `python3 cli.py fetch labels --entity instrument` for the pattern), the target language list is:

`hu, es, fr, en, de, cs, uk, it, hr, pl, ru, nl` (Hungarian, Spanish, French, English, German, Czech, Ukrainian, Italian, Croatian, Polish, Russian, Dutch)

English is fetched too but only kept when it differs from whatever the row's existing base/default name already is (see `python3 cli.py load names --entity instrument`) -- avoids a redundant duplicate row for the common case where the base name already came from Wikidata's English label. `fetch_wikidata_relationships.py`'s `TARGET_LANGUAGES` is the single source of truth for this list; keep it and this section in sync if it changes.

`translate_nationalities.py`'s hand-written `TRANSLATIONS` dict is a separate, non-Wikidata source for nationality-tag translations (used because `nationalities` rows aren't Wikidata entities with their own QIDs). When adding or checking an entry there, especially for a compound/ethnonym term, verify it against that language's *own* Wikipedia usage for a real example (e.g. that specific composer's own-language article) rather than pattern-matching the spelling other languages use — several "Franco-Flemish" entries were wrong this way, guessed from each language's native word for "French" instead of the actual musicological loanword (hu/de/cs/uk/pl/hr all use a transliterated "franko-" prefix, not a translation of "French"; fr/it/es/ru happened to already be right since their native word for "French" *is* the loanword root).

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

1. **Source → CSV**: Each era has its own CSV under `data/eras/` (`data/eras/composers_Medieval.csv`, `data/eras/composers_Baroque.csv`, ...), columns `article,name,birth,death,nationality[,era]`; the Hungarian-language list is `data/composers_Hungarian.csv` (sits directly under `data/`, not `data/eras/`, since it's a language split rather than an era). `parse_hu_wiki_composers.py` is the pattern for turning a raw Wikipedia list wikitext dump (e.g. `zeneszerzok_hu_wiki.txt`) into one of these CSVs — bullet-list wikilinks (`*[[Article|Display]] (birth – death)`) parsed into rows, with hand-maintained `ERA_OVERRIDES` for composers whose era isn't derivable from the source list itself.
2. **CSV → DB**: `load_composers.py` loads the English-language era CSVs (`SOURCES` dict), merging a composer onto an existing row by their normalized `en` wikilink title (falling back to exact name match for composers with no Wikipedia page), so rerunning it is idempotent. `load_hungarian_composers.py` does the equivalent for `data/composers_Hungarian.csv`, but merges by (birth year, death year, name-as-a-set-of-words) instead — this catches same-alphabet reordering (Hungarian "Ligeti György" ↔ existing "György Ligeti") but *not* translated or transliterated names, which land as new rows.
3. **Dedup**: `find_duplicate_composers.py` reports composers sharing an exact birth+death year (narrowed to groups touching a non-`en` wikilink, otherwise too noisy — most collisions among the thousands of other composers are coincidental). This is the tool for finding same-person-different-spelling duplicates (translated names, Russian transliterations, etc.) that the loaders' automatic matching misses. Nothing here is auto-merged — `merge_composers.py <keep_id> <drop_id> <language>` does the actual merge once you've confirmed a pair by hand.
4. **Classification**: `classify_hu_wiki_composers.py` flags Hungarian-list composers who are pop/rock/light-music figures rather than concert-music composers, using hu.wikipedia.org category membership via the MediaWiki API (cached in `hu_wiki_categories_cache.json`). It's a heuristic (category keyword match, e.g. `Kategória:Magyar könnyűzenei előadók`), not authoritative — writes `flag`/`flag_reason` columns back onto `data/composers_Hungarian.csv` rather than deleting anything, so wrong flags get fixed by hand later. `load_hungarian_composers.py` skips rows with `flag == 'pop'`.

Running the whole pipeline from scratch: apply `schema.sql`, then `python3 load_composers.py`, then `python3 load_hungarian_composers.py`.

## Tests

`test.py` and `test_investigate_wikipedia_pages.py` use pytest, but pytest is **not currently installed** in `.venv` — install it first (`pip install pytest`) before trying to run them.
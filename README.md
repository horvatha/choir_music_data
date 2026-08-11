# Composer database project

This project is about collecting composer data and share them via Internet.
There is a plan for getting relationships (father, teacher...) using NLP or simpler tool and investigate that network.
If this project can give back to the data sources we use, it will.
(I still [made some corrections](https://en.wikipedia.org/wiki/Special:Contributions/Harp) in the Wikipedia composer lists when I found some typo or misleading information.)

You can see the [collected data](https://pyedu.hu/arpad/composers/) here.

If you want to participate in this project, or you can give me some data, [reach me](https://pyedu.hu/arpad/email.png).

## Lists of composers used so far

From this page: https://en.wikipedia.org/wiki/Lists_of_composers

- List of Medieval composers
- List of Renaissance composers
- List of Baroque composers
- List of Classical-era composers
- List of Romantic-era composers
- List of 20th-century classical composers
- List of 21st-century classical composers

## How to collect data?

- table data: using the A1*.ipynb notebooks
- lists: using fetch_wikipedia.py

## Fetcher and loader scripts

The live pipeline pulls composer/work/place/instrument data from Wikidata
into `wikidata_relationships.json` (a local cache, gitignored) via `cli.py
fetch ...` commands (or a handful of remaining standalone `fetch_*.py`
scripts for jobs that don't fit the shared shape), then `cli.py load ...`
commands (or standalone `load_*.py` scripts) read that cache and write
into Postgres. `cli.py backfill cache` is a one-time catch-up pass for
data added to the fetch after some composers were already fetched. See
CLAUDE.md for the full schema and the day-to-day workflow; this is just a
map of what each command/script does.

### Pipeline rules (read this before running anything)

**What's in `cli.py` vs. standalone.** A script only got folded into
`cli.py` when it was one of 3+ near-identical scripts differing only by a
config value (which table, which cache key, which entity type). Everything
else stayed standalone, for one of these reasons:
- **Ordering/transactional dependency with another script.**
  `load_genres.py`/`load_musical_keys.py` create a genre/key's own id and
  load its name translations in the *same* transaction; `load_work_instruments.py`
  has a hard-documented 4-step run order shared with three other scripts.
  Splitting either into a separately-invoked `cli.py` command would cost an
  extra DB round-trip or break the ordering.
- **One-off/historical, nobody reruns these regularly.** Frozen crawls
  (the LFZE pair), diagnostic dumps (`fetch_full_wikidata_dump.py`),
  already-fully-applied backfills (`backfill_russian_labels.py`).
- **Fetch+load combined by design.** `fetch_famous_composer_names.py`
  also writes `composer_alt_names` directly, unlike every other fetcher
  (which only ever writes the JSON cache).
- **Genuinely unique logic, not a duplicate of anything.**
  `load_nationalities.py` parses free text, `load_place_hierarchy.py` has
  its own hand-maintained place dicts, `load_birth_death_places.py` does
  its own place-history merging -- nothing else shares their shape.
- **A different paradigm entirely.** `load_composers.py`/
  `load_hungarian_composers.py` read the original era CSVs, not the
  Wikidata JSON cache -- that's the documented "live pipeline" (see
  CLAUDE.md), a separate thing from the Wikidata-cache dance every other
  fetch/load script does.

**Full rebuild vs. incremental.** Most loaders **fully rebuild** their
table(s) every run (`TRUNCATE` first) -- rerunning after a fresh fetch is
the intended way to pick up upstream changes, not something to avoid. A
few are genuinely incremental (only touch composers/entities not yet
loaded); each script's own docstring says which.

**Hard run-order dependencies within one session:**
1. `promote_new_composer_entries.py` must run once after
   `load_missing_composers.py` inserts new composers, before *any* other
   loader will see them -- `applied_to_db` isn't set on a new composer's
   cache entry until this runs, and every loader below checks that flag
   and silently skips entries missing it.
2. `load_instruments.py` → `load_work_instruments.py` →
   `cli.py fetch labels --entity instrument` →
   `cli.py load names --entity instrument` → `load_instrument_groups.py`.
   `load_instruments.py`'s `TRUNCATE ... CASCADE` wipes
   `work_instruments`/`instrument_names` too (a real FK cascade, not
   incidental) -- all four downstream steps need rerunning after it, not
   just the ones that look instrument-specific.

**Two gotchas that will bite you if you don't know about them:**
- *Stale cache ids after a merge.* `merge_composers.py` deletes the
  `drop_id` row from `composers`, but the Wikidata JSON cache still has an
  entry keyed by that old numeric id -- nothing rewrites the cache on a
  merge. `load_instruments.py`/`load_composer_relations.py`/
  `load_works.py`/`load_missing_wikilinks.py` all check for this and
  skip+count rather than crash (a crash here is safe -- the whole run
  rolls back as one transaction -- but achieves nothing). If you write a
  new loader that inserts using a cache key as `composer_id` directly,
  give it the same guard.
- *Concurrent cache writes silently lose data.* Every fetch/backfill
  command reads the whole JSON cache into memory once and periodically
  writes its entire copy back -- running two at the same time means
  whichever finishes a write last wins, silently discarding the other's
  progress. Never run two `cli.py fetch ...`/`cli.py backfill ...`
  invocations (or a standalone fetch/backfill script) at the same time
  against the same cache file.

**Hand-maintained exceptions.** Several loaders carry a small,
hand-reviewed override/exclusion dict for cases where Wikidata's own
claims are technically correct but not useful for this database -- a
deliberate judgment call, not a bug:
- `load_works.py`'s `EXCLUDED_QIDS` -- non-musical "notable work" claims
  for composers with a second career (E.T.A. Hoffmann's novels, William
  Herschel's astronomy papers).
- `load_composer_relations.py`'s `EXCLUDED_RELATIONS` -- same reasoning
  for non-musical relationship claims (Herschel's astronomy doctoral
  advisor and student).
- `load_tags.py`'s `EXCLUDED_QIDS`/`QID_REDIRECTS` -- `P135` "movement"
  values that aren't real, usable movement concepts (dropped), and one
  mistagged movement folded into the one it should have been (a composer
  carrying Q14378 "Neoclassicism," the general art-historical movement,
  redirected to Q535611, the musical one -- easy to confuse since musical
  Neoclassicism took its name from the earlier movement as a deliberate
  allusion).
- `load_names.py`'s `INSTRUMENT_NAME_OVERRIDES` -- two distinct
  instruments whose Wikidata label collides in a given language.
- `parse_hu_wiki_composers.py`'s `ERA_OVERRIDES`, `load_place_hierarchy.py`'s
  hardcoded place dicts -- same pattern, different domain.

Adding a new exception means editing the relevant dict by hand with a
one-line comment explaining why -- there's no automated way to detect
these; they're found by reviewing what a fetch actually pulled in for a
specific composer, same as the doctoral-advisors review that found
Herschel's.

### `cli.py`: consolidated commands

Run `python3 cli.py --help`, or `--help` on any subcommand, for full option
lists.

| Command | Replaces (history) | Purpose |
|---|---|---|
| `fetch composers --era/--nationality/--ids` | `fetch_wikidata_relationships.py`, `fetch_wikidata_by_era.py`, `fetch_wikidata_for_composer_ids.py` | Main fetch: relationships (father/mother/teacher-student/...), cross-language name labels, and attributes (citizenship, movement, genre, instrument, notable work, ...) for composers, selected by nationality, era, or explicit id. |
| `fetch composer-names --ids/--curated` | `fetch_curated_composer_names.py`, `fetch_full_language_names_for_composers.py` | Fetches *every* Wikidata language for composers whose name genuinely differs per language (royalty, translated epithets like "the Elder"), not just the base set `fetch composers` asks for. |
| `fetch labels --entity` | `fetch_instrument_names.py`, `fetch_country_names.py`, `fetch_genre_names.py`, `fetch_key_names.py` | Fetches an instrument/country/genre/key's name in every target (or, for genre/key, every available) language. |
| `fetch candidates INPUT_PATH` | `fetch_candidate_people.py` | Fetches full Wikidata data for an arbitrary QID list (e.g. relation-graph discovery candidates), regardless of whether they turn out to be composers. |
| `load names --entity` | `load_country_names.py`, `load_instrument_names.py`, `load_place_names.py`, `load_work_names.py` | Loads `<entity>_names` translations from the corresponding label cache. |
| `backfill cache --field` | `backfill_dates.py`, `backfill_relationships.py`, `backfill_sitelinks.py`, `backfill_wikidata_attributes.py` | One-time catch-up: patches a missing/stale field into every already-fetched composer's cache entry. |

### Composers: core

| Script | Purpose |
|---|---|
| `fetch_wikidata_relationships.py` | Shared helpers/constants (`api_get`, `get_entity`, `extract_*`, `TARGET_LANGUAGES`, ...) used by nearly every fetch/backfill command above and script below. No longer has its own entry point -- see `cli.py fetch composers`. |
| `fetch_full_wikidata_dump.py` | Diagnostic one-off: dumps a QID's *entire* raw Wikidata entity, unfiltered, for inspection. Not part of the DB pipeline. |
| `load_composers.py` | Loads the English-language era CSVs (`composers_Medieval.csv`, etc.) into `composers`. |
| `load_hungarian_composers.py` | Merges `composers_Hungarian.csv`, skipping rows flagged `pop` by `classify_hu_wiki_composers.py`. |
| `load_composer_relations.py` | Loads `composer_relations` from the fetched relationship props. |
| `load_composer_alt_names.py` | Loads `composer_alt_names` from every language a composer's Wikidata entity has a label in. |
| `load_birth_death_places.py` | Loads exact birth/death dates and resolves birth/death places to their historical (name, country) window. |
| `load_nationalities.py` | Parses the free-text `composers.nationality` column into the normalized `nationalities`/`composer_nationalities` tables. |

### Backfills (one-time catch-up)

| Script | Purpose |
|---|---|
| `backfill_russian_labels.py` | Adds a Russian label for composers with a Soviet/Russian-Empire signal but no nationality tag to key a Russian fetch off of. |
| `backfill_wikidata_ids_from_relations.py` | Backfills `wikidata_id` for composers who only ever showed up as an unlinked target of someone else's relation. |
| `backfill_wikidata_ids_from_wikilinks.py` | Backfills `wikidata_id` by matching a composer's own Wikipedia article against Wikidata's sitelinks. |
| `backfill_manual_alt_names.py` | Loads a small set of hand-constructed `composer_alt_names` not sourced from Wikidata at all (e.g. disambiguating "the Elder"/"the Younger" pairs where Wikidata gives both the same name). |

### Instruments

| Script | Purpose |
|---|---|
| `fetch_instrument_classification.py` | Fetches Hornbostel-Sachs codes and P279 ancestor sets, used to sort instruments into groups. |
| `load_instruments.py` | Loads `instruments`/`composer_instruments` from the fetched `instrument` attribute. |
| `load_instrument_groups.py` | Defines the `instrument_groups` taxonomy and assigns every instrument to one. |
| `load_lfze_instruments.py` | Loads hand-curated composer/instrument facts (with citation) from Nagy elodok bios, for facts with no Wikidata claim yet. |

### Genres and musical keys

| Script | Purpose |
|---|---|
| `load_genres.py` | Loads `genres`/`genre_names`/`work_genres` from the fetched genre data (calls `load_names.upsert_entity_names()` for the name-loading half). |
| `load_musical_keys.py` | Loads `musical_keys`/`musical_key_names`/`work_musical_keys` (same pattern as `load_genres.py`). |

### Works

| Script | Purpose |
|---|---|
| `fetch_work_details.py` | Fetches each work's name in every language, plus other claims (dates, catalog code, tonality, instrumentation, CPDL ID, ...). |
| `fetch_work_instrument_labels.py` | Resolves a display name for instrumentation QIDs not already known. |
| `load_works.py` | Loads `works` from the fetched `notable_work` attribute. |
| `load_work_dates.py` | Loads `works.composed_*`/`premiered_*`/`published_*`. |
| `load_work_catalog_info.py` | Loads `works.catalog_code` and `works.cpdl_id`. |
| `load_work_instruments.py` | Loads `work_instruments`, reusing the `instruments` table. |

### Places and geography

| Script | Purpose |
|---|---|
| `fetch_place_history.py` | Fetches a place's full history: country-over-time, official-name-over-time, predecessor/successor links, coordinates. |
| `fetch_us_states.py` | Fetches each U.S. place's state by climbing Wikidata's administrative-territorial-entity chain. |
| `load_place_hierarchy.py` | Sets `place_type` and `parent_place_id` for places administratively part of a larger tracked place. |
| `load_us_states.py` | Loads `states` and `places.state_id`. |

### Hungarian sources

| Script | Purpose |
|---|---|
| `fetch_hu_names.py` | Fetches Hungarian-specific names for countries/places/works already referenced in the cache. |
| `fetch_lfze_nagy_elodok.py` | Crawls the Liszt Academy's "Nagy elodok" biographical pages. |
| `load_lfze_nagy_elodok.py` | Loads the confirmed composers from that crawl into `other_webpages`. |

### Misc

| Script | Purpose |
|---|---|
| `fetch_new_21st_century_wikidata.py` | Cross-checks a new Wikipedia list snapshot against the DB and fetches Wikidata data for composers not yet loaded. |

## TODO

- Creating list of composers, removing duplicates
- Fetching the missing articles from Wikipedia
  (see save_articles_from_xml.py and investigate_wikipedia_pages.py)
  and handling redirects, false articles
- Creating unified table and removing duplicates
- Sanity checking
- Web page
- Search in Web page
- There is a plan for getting relationships (father, teacher...) using NLP or simpler tool.
- Find composers not on these lists, like some from here https://en.wikipedia.org/wiki/Category:Cuban_classical_composers

## Useful data

- Useful music databases https://libguides.butler.edu/c.php?g=34052&p=216855
- https://www.naxos.com/feature/Naxos-Works-Database.asp

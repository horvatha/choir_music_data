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

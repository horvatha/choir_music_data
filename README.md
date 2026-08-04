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
into `wikidata_relationships.json` (a local cache, gitignored) via the
`fetch_*.py` scripts, then `load_*.py` scripts read that cache and write
into Postgres. `backfill_*.py` scripts are one-time catch-up passes for
data added to the fetch after some composers were already fetched. See
CLAUDE.md for the full schema and the day-to-day workflow; this is just a
map of what each script does.

### Composers: core

| Script | Purpose |
|---|---|
| `fetch_wikidata_relationships.py` | Main fetch: relationships (father/mother/teacher-student/...), cross-language name labels, and attributes (citizenship, movement, genre, instrument, notable work, ...) for composers, selected by nationality. |
| `fetch_wikidata_by_era.py` | Same as above, but selects composers by era instead of nationality. |
| `fetch_wikidata_for_composer_ids.py` | Same as above, but targets exact composer IDs (e.g. composers with no nationality set). |
| `fetch_full_wikidata_dump.py` | Diagnostic one-off: dumps a QID's *entire* raw Wikidata entity, unfiltered, for inspection. Not part of the DB pipeline. |
| `load_composers.py` | Loads the English-language era CSVs (`composers_Medieval.csv`, etc.) into `composers`. |
| `load_hungarian_composers.py` | Merges `composers_Hungarian.csv`, skipping rows flagged `pop` by `classify_hu_wiki_composers.py`. |
| `load_composer_relations.py` | Loads `composer_relations` from the fetched relationship props. |
| `load_composer_alt_names.py` | Loads `composer_alt_names` from every language a composer's Wikidata entity has a label in. |
| `load_birth_death_places.py` | Loads exact birth/death dates and resolves birth/death places to their historical (name, country) window. |
| `load_nationalities.py` | Parses the free-text `composers.nationality` column into the normalized `nationalities`/`composer_nationalities` tables. |
| `fetch_curated_composer_names.py` | Fetches *every* Wikidata language for a small hand-picked list of composers whose name genuinely differs per language (royalty, translated epithets like "the Elder"), not just the base set `fetch_wikidata_relationships.py` asks for. |

### Backfills (one-time catch-up)

| Script | Purpose |
|---|---|
| `backfill_dates.py` | Day-level-precision birth/death dates for composers fetched before date support existed. |
| `backfill_relationships.py` | Rechecks relationships for composers fetched before `child`/`spouse` were added to the fetched props. |
| `backfill_russian_labels.py` | Adds a Russian label for composers with a Soviet/Russian-Empire signal but no nationality tag to key a Russian fetch off of. |
| `backfill_sitelinks.py` | Fetches sitelinks (which Wikipedias a composer has an article in) for composers fetched before sitelink support existed. |
| `backfill_wikidata_attributes.py` | Re-fetches attribute props for every composer already on file with a QID. |
| `backfill_wikidata_ids_from_relations.py` | Backfills `wikidata_id` for composers who only ever showed up as an unlinked target of someone else's relation. |
| `backfill_wikidata_ids_from_wikilinks.py` | Backfills `wikidata_id` by matching a composer's own Wikipedia article against Wikidata's sitelinks. |
| `backfill_manual_alt_names.py` | Loads a small set of hand-constructed `composer_alt_names` not sourced from Wikidata at all (e.g. disambiguating "the Elder"/"the Younger" pairs where Wikidata gives both the same name). |

### Instruments

| Script | Purpose |
|---|---|
| `fetch_instrument_names.py` | Fetches each instrument's name in every target language. |
| `fetch_instrument_classification.py` | Fetches Hornbostel-Sachs codes and P279 ancestor sets, used to sort instruments into groups. |
| `load_instruments.py` | Loads `instruments`/`composer_instruments` from the fetched `instrument` attribute. |
| `load_instrument_names.py` | Loads `instrument_names` translations. |
| `load_instrument_groups.py` | Defines the `instrument_groups` taxonomy and assigns every instrument to one. |
| `load_lfze_instruments.py` | Loads hand-curated composer/instrument facts (with citation) from Nagy elodok bios, for facts with no Wikidata claim yet. |

### Genres and musical keys

| Script | Purpose |
|---|---|
| `fetch_genre_names.py` | Fetches each genre's name in every language Wikidata has. |
| `load_genres.py` | Loads `genres`/`genre_names`/`work_genres` from the fetched genre data. |
| `fetch_key_names.py` | Fetches each musical key's (tonality's) name in every language Wikidata has. |
| `load_musical_keys.py` | Loads `musical_keys`/`musical_key_names`/`work_musical_keys`. |

### Works

| Script | Purpose |
|---|---|
| `fetch_work_details.py` | Fetches each work's name in every language, plus other claims (dates, catalog code, tonality, instrumentation, CPDL ID, ...). |
| `fetch_work_instrument_labels.py` | Resolves a display name for instrumentation QIDs not already known. |
| `load_works.py` | Loads `works` from the fetched `notable_work` attribute. |
| `load_work_names.py` | Loads `work_names` translations. |
| `load_work_dates.py` | Loads `works.composed_*`/`premiered_*`/`published_*`. |
| `load_work_catalog_info.py` | Loads `works.catalog_code` and `works.cpdl_id`. |
| `load_work_instruments.py` | Loads `work_instruments`, reusing the `instruments` table. |

### Places and geography

| Script | Purpose |
|---|---|
| `fetch_place_history.py` | Fetches a place's full history: country-over-time, official-name-over-time, predecessor/successor links, coordinates. |
| `fetch_us_states.py` | Fetches each U.S. place's state by climbing Wikidata's administrative-territorial-entity chain. |
| `fetch_country_names.py` | Fetches each country's name in every target language. |
| `load_place_names.py` | Loads `place_names` translations. |
| `load_place_hierarchy.py` | Sets `place_type` and `parent_place_id` for places administratively part of a larger tracked place. |
| `load_country_names.py` | Loads `country_names` translations. |
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

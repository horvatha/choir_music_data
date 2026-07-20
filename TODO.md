# TODO

## Country-as-place bug: 34 composers, 10 recovered by hand from Wikipedia prose

Found 2026-07-20: `place_of_birth`/`place_of_death` in Wikidata equal to
`citizenship` for the same person (a country QID recorded as if it were
a specific city -- e.g. Jan Van der Roost's P20 claim is literally `Q31`
Belgium) affected 34 composers (19 birth, 16 death, Duarte Lobo both).
Fixed by clearing the bogus `birth_place_id`/`death_place_id` rather than
show a country pretending to be a place.

All 34 were then individually re-checked against their English Wikipedia
article's actual prose (not just Wikidata's structured claims, which is
all this repo's pipeline normally reads) to see if a specific place was
recoverable that way. 10 were -- corrected by hand, place created from
Wikidata when the place had its own QID (Alcáçovas, Brihuega, Camagüey,
Delvinë, Hamburg, Tirana, Budapest, New York City, Mexico City all
already existed or were created the normal way), or created manually
from just the article text when no Wikidata item exists at all (Siloam,
South Africa -- Hannes Taljaard's birthplace):

  - Duarte Lobo (819): born Alcáçovas, Alentejo, Portugal.
  - Sebastián Durón (1270): born Brihuega, Guadalajara, Spain.
  - María de las Mercedes Adam de Aróstegui (2970): born Camagüey, Cuba.
  - Ferdinand David (2195): born Hamburg -- same house Felix Mendelssohn
    was born in the previous year, per the article.
  - Allen Shawn (5275): born New York City.
  - Limoz Dizdari (6510): born Delvinë, Albania.
  - Aleksandër Peçi (6512): born Tirana, Albania.
  - Hannes Taljaard (7223): born Siloam, Venda, South Africa.
  - Havasi Balázs (7562): born Budapest.
  - María Teresa Prieto (3467): died Mexico City.

One more (Charles Camilleri, died Naxxar, Malta) was found but
deliberately left unfixed -- the article only says he lived there and
was buried there, doesn't state it as where he died, too inferential to
apply with confidence.

The remaining 23 were confirmed to genuinely have no more specific place
recoverable from the article prose either -- mostly because the person
is still living (no death to place at all), or the article itself only
gives a country/region with no source for anything narrower.

## "City of London" (place 1269) has the wrong Wikidata QID

Found while wiring up London's borough hierarchy (2026-07-20). Place 1269
is named "City of London" but its `place_qids` entry is `Q92561`, which
is actually **London, Ontario, Canada** -- a different place entirely.
The real City of London (the historic Square Mile) is `Q23311`, already
correctly present as a separate place (id 2016) and now linked into
Greater London's district hierarchy. Not fixed -- pre-existing data
issue, unrelated to today's work, just noticed in passing. Whichever
composer(s) currently reference place 1269 need checking: are they
really tied to London, Ontario (in which case the place just needs
renaming to stop it looking like a duplicate), or did the wrong QID get
attached to a composer who's actually tied to the real City of London
(in which case they should be repointed to place 2016 instead)?

## backfill_wikidata_ids_from_relations.py name-matching: confirmed misfire

`backfill_wikidata_ids_from_relations.py`'s own docstring already warned
this can misfire when two different real people share a name (citing two
different "Michael Praetorius"es). Found a second, confirmed case
2026-07-20: composer 1655 (Thomas Arne, the composer, Q309709) had
`wikidata_id` wrongly set to `Q18528713` -- his own father, also named
Thomas Arne (an upholsterer, not a musician), a different Wikidata item
entirely. This produced two visible bugs: Thomas Arne's own composer
page showed himself as his own father (composer_relations self-link, via
`load_composer_relations.py` cross-referencing `composers.wikidata_id`),
and his son Michael Arne's page showed "Thomas Arne" as father with no
link at all (the QID composer_by_qid needed, Q309709, wasn't attached to
any composer since 1655 had the wrong one). Fixed by hand: corrected
`composers.wikidata_id` to Q309709 (verified via the wikilink-title
method, which already gave the right answer independently) and reran
`load_composer_relations.py`.

Worth a systematic pass: any composer whose `wikidata_id` came from
`backfill_wikidata_ids_from_relations.py` (name-matched, not title-
matched) rather than `backfill_wikidata_ids_from_wikilinks.py` is at risk
of this exact failure mode, especially anyone sharing a name with a
close relative (fathers/sons with the same name are the obvious case,
per this one).

## Munkács/Mukachevo: Wikidata's own P17 data is incomplete

Checked as a stress test for the place-history/predecessor work below.
Munkács (hu) / Mukachevo (Q146456) is a single Wikidata item (unlike
Budapest -- no separate QIDs to merge, structurally like Moscow), so the
existing per-QID multi-window mechanism already handles this *shape* of
problem (one continuously-named place, country changes over the 20th
century: Austria-Hungary -> Czechoslovakia -> Hungary -> Soviet Union ->
Ukraine) with no new code needed.

But Wikidata's own P17 claims for this item are incomplete: only 3
claims, none with P580/P582 (start/end) qualifiers, and missing
Czechoslovakia and the Soviet era entirely (only Austria-Hungary,
Austrian Empire, and Ukraine are present). So even once resolved, a
composer born there would currently show just "Ukraine" regardless of
birth year, until Wikidata's own data improves -- nothing to fix on our
end; this is a source-data gap, not a pipeline bug. No composer is
currently tied to this place (checked), so not urgent.

## Places' country isn't time-aware

`places.country_id` stores a single static country per place, but many
places' actual country affiliation changed over history (e.g. Moscow:
Duchy of Moscow → Tsardom of Russia → Russian Empire → Soviet Union →
Russia). A composer's birth/death place shows whatever single country got
picked, regardless of which century that composer actually lived in --
e.g. Prokofiev (died 1953, USSR) currently shows "Duchy of Moscow" for his
death place, which is centuries off; "Russia" (the modern country) would
be closer but still wrong for 1953 -- it should be "Soviet Union" for that
specific date. Neither a fixed "always current" nor a fixed "always
earliest" choice is right; the correct country genuinely depends on which
year within the place's history is being asked about.

Two separate things going on, worth fixing separately:

1. **Quick, well-scoped fix**: `extract_first_qid()` in
   `fetch_place_countries.py` doesn't check Wikidata's claim `rank` at
   all -- it just takes the first non-deprecated P17 claim, which can
   land on an arbitrary historical claim instead of the "preferred"
   (current) one. Moscow (Q649) has 8 P17 claims, one of them ranked
   "preferred" (→ Russia, the current country) -- fixing this rank
   check (same pattern as the `extract_p131` rank fix in
   `fetch_us_states.py`) would at least stop picking essentially-random
   historical claims and default consistently to the *current* country.
   Still not date-correct for historical composers, but a clear
   improvement over what's there now.

2. **The actual fix (harder, deferred)**: resolve a place's country
   *as of* the composer's birth/death year, using each P17 claim's
   P580 (start time) / P582 (end time) qualifiers to pick whichever
   claim's date range covers that year, falling back to the
   "preferred" claim when no dated claim covers it (e.g. very old
   dates, or a composer with no known birth/death year at all).
   Requires: storing multiple (country, start, end) rows per place
   instead of a single `places.country_id` -- probably a new
   `place_countries_by_period` table -- and passing the relevant
   composer's birth/death year through to whatever resolves the
   display country, rather than resolving it once per place
   independent of who's asking.

## ~~Buda/Pest/Óbuda aren't clustered into Budapest~~ (done, via place_predecessors)

Resolved, but *not* via `MANUAL_PLACE_CLUSTERS` (that was tried first and
reverted -- see below). Buda's and Pest's own Wikidata items each carry a
sloppy open-ended modern-era P17 claim (Buda: Hungary from 1946-None;
Pest: Hungary from 1918-None) that isn't really wrong but breaks
`load_birth_death_places.py`'s window-merging algorithm: whichever QID
in the cluster gets processed first with an open-ended claim causes
everything else in the cluster to be discarded, since the algorithm
assumes only the chronologically-last QID has one. Attempting the
Königsberg/Kaliningrad-style full merge collapsed Buda's and Pest's real
separate histories into one blank pre-1873 "Budapest" row -- a regression
caught before committing, reverted.

Used a lighter mechanism instead: a new `place_predecessors` table
(place_id -> predecessor_place_id, many-valued, with a display_order)
that links Buda/Pest/Óbuda to Budapest for composer-listing purposes only
-- each keeps its own `places`/`place_periods` rows rather than being
merged into one timeline. `concert_music_app`'s place detail page now
shows a "Parts that were separate places before" section listing each
predecessor with its own composers. See the table's comment in
`schema.sql` / `migrate_place_predecessors.sql`.

## backfill_wikidata_ids_from_wikilinks.py: extract_years() ignores precision

Found via composer 3034 (Eugenia Calosso): her Wikidata death claim is
`+2000-00-00T00:00:00Z` with `precision: 7` (century-level -- Wikidata
only knows she died sometime in the 20th/21st century, encoded as a round
century-boundary timestamp), not a real claim of dying in the year 2000.
`extract_years()` reads the year digits regardless of precision, so this
showed up as a false "death year mismatch" (ours=1914 vs "2000") even
though it's not a real conflict at all -- her birth claim (precision 11,
exact day) matches ours perfectly, confirming same person.

Fix: only trust a P569/P570 claim's year when precision >= 9 (year-level
or finer -- 9=year, 10=month, 11=day), same reasoning `extract_dates()`
in fetch_wikidata_relationships.py already applies (it requires precision
== 11 specifically, for exact-date purposes; this only needs >= 9 since
it's just comparing years). Below that (7=century, 8=decade), treat the
claim as unknown rather than comparing it.

This likely explains some fraction of the ~202 remaining "no
corroboration" cases below -- worth fixing and re-running the comparison
before manually reviewing what's left, since some may turn out to be
false alarms exactly like Calosso.

## ~202 unreviewed wikilink-backfill year mismatches

`backfill_wikidata_ids_from_wikilinks.py` linked 4014 composers via their
Wikipedia article's Wikidata sitelink, plus 183 more confirmed by an
exact matching death year. What's left: composers whose article-derived
QID has birth/death years that don't corroborate ours on either end --
some are genuinely different people who happen to share a name (verified:
Louis Aubert, Edvard Hagerup Bull), some are wrong redirects/matches
(verified: Jean Mignon, Storm Bull, George Tibbits), some are our own
source data being wrong (verified: Johann Melchior Gletle -- a 300-year
"19"-for-"16" error traced to composers_20th_century.csv itself), and
some are the same person with just uncertain/imprecise dates on one or
both sides (verified: Francesco Rognoni, Lucas Ruiz de Ribayaz, Pedro de
Escobar, Eugenia Calosso -- the last one turning out to be the precision
bug above, not a real mismatch).

No shortcut found yet for telling these apart automatically beyond what's
already implemented (exact death-year match); the rest need judgment
per-composer the way Gletle/Calosso were resolved. Should also fix the
precision bug above and re-run first, since that will likely resolve or
reclassify some of these before manual review.

## country_names only ever stores a Hungarian translation

`load_country_names.py` hardcodes `'hu'` in its INSERT -- `country_names`
was only ever built to hold one language, unlike `place_names` (which
properly caches hu/en/de/ru via `fetch_place_history.py`'s
`place_labels`). So no country ever gets a Russian or German name, by
design, not by bug. Found via composers/2456 (Franz Lehár): his death
place's country, "Allied-occupied Austria" (Q596239), shows the same
English string in both EN and HU views -- partly because no other
language is ever fetched/stored for countries at all, and partly because
this specific country is brand new (created by today's
load_birth_death_places.py run) and hasn't had `fetch_hu_names.py` run
for it yet either.

Fix would mean generalizing country name fetching/loading to hu/de/ru the
same way places already work, rather than the current hu-only, one-off
`fetch_hu_names.py`/`load_country_names.py` pair.

## Spot-check composers_20th_century.csv for other bad rows

The Gletle case (see above) suggests composers_20th_century.csv may have
other misattributed/fabricated-looking entries beyond just wrong dates --
worth spot-checking a sample of the file for entries that look
suspicious (composer clearly belongs to a different era, unfamiliar
"notable work" titles, etc.) rather than assuming it's an isolated case.

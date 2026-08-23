"""Load composers found via the teacher/student/parent/child relations of
composers already in the DB (see fetch_missing_composers_from_relations.py,
fetch_candidate_people.py) -- first step only: creates a composers row
(name + wikidata_id, nothing else yet -- birth/death/nationality/
relationships are a later step) plus composer_alt_names, for whichever
candidates' English Wikidata description actually mentions "composer".

Not scoped to any one source/round -- operates on every "new:" entry in
the cache regardless of which fetch script produced it (round 1 via
missing_composers_from_relations.csv, round 2 via the split
fetch_candidate_people.py run, ...); already-loaded composers are skipped
via the wikidata_id existence check, so reruns after a fresh round of
fetching only touch the newly-qualifying ones.

That description-substring filter is deliberately blunter than checking
P106 occupation values (which is how the candidate list was built in the
first place, and turned out too loose -- e.g. Luigi Torchi has "composer"
somewhere in his P106 claims but Wikidata's own description calls him an
"Italian musicologist", and his Wikipedia article doesn't foreground
composing either). Requiring the word in the description is a cheap,
no-further-fetch way to cut a lot of that noise; not perfect, but good
enough for a first pass -- see chat for the by-hand sample review that
motivated this.

The substring check alone still passes relatives of composers whose
description is *about* the relation, not the person's own occupation --
e.g. Gustav Mahler's mother Marie Herrmann's description is "mother of
composer Gustav Mahler". NON_COMPOSER_RELATION_PATTERN excludes any
description matching "<relation word> of ... composer" (mother/father/
wife/son/pupil of/etc.) before the substring check runs; 38 such rows
(Mahler's, Rossini's, Wagner's, J.S. Bach's and others' relatives) were
found already loaded and deleted by hand on 2026-08-11 before this filter
existed.

Checking only the English description also misses real composers whose
English label is vaguer than their other-language ones -- e.g. Amanda
Röntgen-Maier's English description is "Swedish musician (1853-1894)"
while German/French/Spanish/Polish/Russian/Dutch all say composer outright
("schwedische Violinistin und Komponistin", "compositrice et violoniste
suédoise", ...). is_composer_description (composer_description_
classification.py) checks every TARGET_LANGUAGES description (not just
"en"), each against its own localized composer-word and relation-word
pattern -- a description only counts
if it mentions the composer word *and* doesn't also read as being about a
relation in that same language. Found via the same by-hand review that
turned up Amanda: of ~6000 still-unlinked notable_student/student_of/
spouse/child/mother/father relations, 570 passed this broader check on a
random-sampled review (2026-08-11) -- not yet bulk-loaded, left for a
deliberate follow-up run.

Alt names loaded: every TARGET_LANGUAGES entry present, same as the rest
of this pipeline, *plus* any other language's label that isn't written in
Latin script (Cyrillic, CJK, Armenian, ...) even when that language isn't
one of the 12 targets -- these people don't have a resolved nationality
yet for the usual NATIVE_LANGUAGE_BY_NATIONALITY lookup to key off of, so
this checks the label's actual script directly instead of guessing a
single "native" language from citizenship.

Also re-keys each newly-inserted composer's cache entry from its "new:<qid>"
key to its real composer_id and marks it applied_to_db -- used to be a
separate manual step (promote_new_composer_entries.py), folded in here
since this loop already knows composer_id right after inserting, no need
for that script's own DB lookup. Every other loader
(load_composer_relations.py, load_instruments.py, load_tags.py,
load_works.py, ...) checks applied_to_db before processing an entry, so
skipping this used to mean no other loader could see a newly-added
composer until a separate script ran.

Usage:
    python3 load_missing_composers.py
"""
import unicodedata

import psycopg2

from adapters.json_cache import load_cache, save_cache
from composer_description_classification import is_composer_description
from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

INSERT_COMPOSER_SQL = "INSERT INTO composers (name, wikidata_id) VALUES (%s, %s) RETURNING id"
CHECK_EXISTING_SQL = "SELECT id FROM composers WHERE wikidata_id = %s"
UPSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO NOTHING
"""


def is_latin_script(text: str) -> bool:
    return all(not ch.isalpha() or unicodedata.name(ch, "").startswith("LATIN") for ch in text)


def _pick_display_name(labels: dict, fallback: str) -> str:
    """en, else a Latin-script label (composers.name is meant to hold the
    international/canonical form -- see CLAUDE.md -- so picking whichever
    label happens to sort first alphabetically by language code, as a
    naive next(iter(...)) would, can land on an Arabic/Cyrillic/CJK label
    ahead of an available Latin one just because "ar"/"arz"/"be" sorts
    before "en"/"fr"/"nl"), else any label at all, else the fallback
    (entry["name"], which in the worst case -- no labels fetched at
    all -- is itself just the bare QID)."""
    if "en" in labels:
        return labels["en"]
    latin = [v for v in labels.values() if is_latin_script(v)]
    if latin:
        return latin[0]
    if labels:
        return next(iter(labels.values()))
    return fallback


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data.get("composers", {})

    candidates = [
        (key, entry) for key, entry in entries.items()
        if key.startswith("new:")
        and is_composer_description(entry.get("descriptions", {}), TARGET_LANGUAGES)
    ]
    print(f"{len(candidates)} candidates pass the description filter")

    conn = psycopg2.connect()
    inserted = 0
    already_present = 0
    alt_names_loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for key, entry in candidates:
                    qid = entry["qid"]
                    cur.execute(CHECK_EXISTING_SQL, (qid,))
                    existing = cur.fetchone()
                    if existing:
                        already_present += 1
                        continue

                    labels = entry.get("labels", {})
                    # entry["name"] can itself be a bare QID (e.g.
                    # "Q4073766") -- fetch_candidate_people.py seeds it
                    # from whatever the source relation list had at
                    # discovery time, which for a person only ever seen as
                    # someone else's notable_student/child/etc. QID (no
                    # display name known yet) is just the QID string
                    # itself.
                    name = _pick_display_name(labels, entry["name"])
                    cur.execute(INSERT_COMPOSER_SQL, (name, qid))
                    composer_id = cur.fetchone()[0]
                    inserted += 1

                    for language, label in labels.items():
                        if language == "en":
                            continue
                        in_target = language in TARGET_LANGUAGES
                        if not in_target and is_latin_script(label):
                            continue
                        cur.execute(UPSERT_ALT_NAME_SQL, (composer_id, language, label))
                        if cur.rowcount:
                            alt_names_loaded += 1

                    # Re-key this cache entry to its real composer_id and
                    # mark it applied_to_db, same as
                    # promote_new_composer_entries.py used to do as a
                    # separate manual step -- folded in here since this
                    # loop already knows composer_id, no need for that
                    # script's own DB lookup. Every other loader
                    # (load_composer_relations.py, load_instruments.py,
                    # load_tags.py, load_works.py, ...) checks
                    # applied_to_db before processing an entry.
                    entries.pop(key)
                    entry["applied_to_db"] = True
                    entries[str(composer_id)] = entry
    finally:
        conn.close()

    if inserted:
        save_cache(OUTPUT_FILE, data)
    print(f"Inserted {inserted} new composers ({already_present} already present, skipped), "
          f"{alt_names_loaded} alt names loaded.")


if __name__ == "__main__":
    main()

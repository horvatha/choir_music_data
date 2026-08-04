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

Alt names loaded: every TARGET_LANGUAGES entry present, same as the rest
of this pipeline, *plus* any other language's label that isn't written in
Latin script (Cyrillic, CJK, Armenian, ...) even when that language isn't
one of the 12 targets -- these people don't have a resolved nationality
yet for the usual NATIVE_LANGUAGE_BY_NATIONALITY lookup to key off of, so
this checks the label's actual script directly instead of guessing a
single "native" language from citizenship.

Usage:
    python3 load_missing_composers.py
"""
import json
import unicodedata

import psycopg2

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


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("composers", {})

    candidates = [
        entry for key, entry in entries.items()
        if key.startswith("new:")
        and "composer" in entry.get("descriptions", {}).get("en", "").lower()
    ]
    print(f"{len(candidates)} candidates pass the description filter")

    conn = psycopg2.connect()
    inserted = 0
    already_present = 0
    alt_names_loaded = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for entry in candidates:
                    qid = entry["qid"]
                    cur.execute(CHECK_EXISTING_SQL, (qid,))
                    existing = cur.fetchone()
                    if existing:
                        already_present += 1
                        continue

                    labels = entry.get("labels", {})
                    name = labels.get("en") or entry["name"]
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
    finally:
        conn.close()

    print(f"Inserted {inserted} new composers ({already_present} already present, skipped), "
          f"{alt_names_loaded} alt names loaded.")


if __name__ == "__main__":
    main()

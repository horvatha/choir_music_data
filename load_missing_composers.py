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
suédoise", ...). _is_composer_description now checks every
TARGET_LANGUAGES description (not just "en"), each against its own
localized composer-word and relation-word pattern in
COMPOSER_WORD_PATTERNS/RELATION_WORD_PATTERNS -- a description only counts
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

Usage:
    python3 load_missing_composers.py
"""
import re
import unicodedata

import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES

NON_COMPOSER_RELATION_PATTERN = re.compile(
    r"\b(mother|father|wife|husband|widow|son|daughter|brother|sister|niece|nephew|cousin|aunt|"
    r"uncle|grandmother|grandfather|grandson|granddaughter|parent|child|spouse|fianc[ée]e?|lover|"
    r"mistress|muse|friend|patron|pupil of|student of|teacher of|relative) of\b.*composer",
    re.IGNORECASE,
)

# Per-language "composer" word stem, for checking descriptions in
# languages other than English (see docstring). Simple substring stems,
# not full-word regexes -- e.g. "compositor" also matches "compositora".
COMPOSER_WORD_PATTERNS = {
    "en": "composer",
    "de": "komponist",
    "fr": "composit",
    "es": "compositor",
    "it": "composit",
    "hr": "skladatelj",
    "pl": "kompozytor",
    "ru": "композитор",
    "uk": "композитор",
    "cs": "skladatel",
    "nl": "componist",
    "hu": "zeneszerz",
}

# Per-language relation-word stems -- basic family/relation vocabulary
# ("mother", "wife", "daughter of", ...), same purpose as
# NON_COMPOSER_RELATION_PATTERN but for the other 11 target languages.
# Not exhaustive grammar, just enough stems to catch "Tochter des
# Komponisten X" / "compositrice, fille de Y" style descriptions that are
# about a relation, not the person's own occupation.
RELATION_WORD_PATTERNS = {
    "de": ("mutter", "vater", "ehefrau", "ehemann", "tochter", "sohn", "witwe", "enkel", "schwester", "bruder"),
    "fr": ("mère", "père", "épouse", "époux", "femme de", "fille de", "fils de", "veuve", "veuf", "sœur", "frère"),
    "es": ("madre", "padre", "esposa", "esposo", "viuda", "viudo", "hija de", "hijo de", "hermana", "hermano"),
    "it": ("madre", "padre", "moglie", "marito", "vedova", "vedovo", "figlia di", "figlio di", "sorella", "fratello"),
    "cs": ("matka", "otec", "manželka", "manžel", "dcera", "syn ", "vdova", "vdovec", "sestra", "bratr"),
    "uk": ("мати", "батько", "дружина", "чоловік", "донька", "дочка", "вдова", "сестра", "брат"),
    "ru": ("мать ", "отец", "жена", "муж ", "дочь", "вдова", "сестра", "брат"),
    "pl": ("matka", "ojciec", "żona", "mąż", "córka", "wdowa", "wdowiec", "siostra", "brat"),
    "hr": ("majka", "otac", "supruga", "suprug", "kći", "udovica", "udovac", "sestra", "brat"),
    "nl": ("moeder", "vader", "echtgenote", "echtgenoot", "dochter", "zoon van", "weduwe", "zus ", "broer"),
    # anya/apa, öcs/báty are irregular in the possessive ("his mother" is
    # "anyja", not "anyája"; "his father" is "apja", not "apája") -- the
    # base forms alone missed Paula Voit ("...zeneszerző édesanyja", "the
    # composer's mother") and Béla Bartók Sr. ("...zeneszerző apja", "the
    # composer's father"), both loaded by mistake on 2026-08-11 before this
    # was caught by hand and these forms were added.
    "hu": ("anya", "anyja", "apa", "apja", "felesége", "férje", "lánya", "fia ", "öccse", "bátyja", "özvegy"),
}

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


def _is_composer_description(descriptions: dict) -> bool:
    en = descriptions.get("en", "")
    if "composer" in en.lower() and not NON_COMPOSER_RELATION_PATTERN.search(en):
        return True
    for language in TARGET_LANGUAGES:
        if language == "en":
            continue
        word = COMPOSER_WORD_PATTERNS.get(language)
        text = descriptions.get(language, "")
        if not word or not text:
            continue
        lower = text.lower()
        if word not in lower:
            continue
        relation_words = RELATION_WORD_PATTERNS.get(language, ())
        if any(rw in lower for rw in relation_words):
            continue
        return True
    return False


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data.get("composers", {})

    candidates = [
        entry for key, entry in entries.items()
        if key.startswith("new:")
        and _is_composer_description(entry.get("descriptions", {}))
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
    finally:
        conn.close()

    print(f"Inserted {inserted} new composers ({already_present} already present, skipped), "
          f"{alt_names_loaded} alt names loaded.")


if __name__ == "__main__":
    main()

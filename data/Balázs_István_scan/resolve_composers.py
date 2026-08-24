"""Resolve every composer name in composers_summary.json against the
composers DB, replacing each name string with [name, wikidata_id, composer_id].

Matching, per name entry:
  1. Split on "|" into surname variants (e.g. "Jommelli | Jomelli").
     A trailing "(Qualifier)" is treated as a given-name hint EXCEPT when
     there's text after the closing paren too (Tinódi (Lantos) Sebestyén),
     where the qualifier is an epithet folded into extra surname variants
     ("Tinódi Lantos Sebestyén" / "Tinódi Lantos") tried alongside the
     bare surname ("Tinódi Sebestyén").
  2. Round 1 -- family-name search across composers.name and
     composer_alt_names.name, word-boundary matched. Priority order:
     Hungarian alt names + accented -> Hungarian + unaccented ->
     any language + accented -> any language + unaccented. Stops at the
     first pass that finds anything.
  3. Round 2 -- if round 1 found more than one composer, narrow using
     the given-name hint (from the parens) and/or the era's approximate
     birth-year range, but never narrow down to zero: a filter that
     would eliminate every remaining candidate is discarded rather than
     applied (safer to flag ambiguous than to silently drop a real match).

Output shape per name:
  - not found at all:      [name, "", -1]
  - exactly one match:     [name, wikidata_id_or_"", composer_id]
  - still ambiguous:       [name, "QID1/QID2/...", one_of_the_ids]
    (QIDs joined for composers that have one; the id is just one
    candidate's id, picked arbitrarily -- the point of this shape is to
    flag "needs a human to pick", not to guess which one.)

Usage:
    python3 resolve_composers.py
"""
import json
import re
import unicodedata
from pathlib import Path

import psycopg2
import psycopg2.extras

HERE = Path(__file__).resolve().parent
INPUT_FILE = HERE / "composers_summary.json"
OUTPUT_FILE = HERE / "composers_summary_resolved.json"

# Rough (composer_id, birth_year) window per era key, used only to break
# ties among an already-ambiguous candidate set -- generous on purpose,
# since these are approximate book-era boundaries, not hard cutoffs.
ERA_BIRTH_YEAR_RANGE = {
    "A középkor zenéje (a 15. század végéig)": (None, 1480),
    "Reneszánsz (16-17. század első fele)": (1420, 1620),
    "Barokk (17. század második fele - 18. század)": (1600, 1800),
    "Klasszikus zene (18. század második fele - 19. század eleje)": (1700, 1830),
    "19. század (Romantika)": (1790, 1910),
    "20-21. század": (1860, None),
}

PAREN_RE = re.compile(r"\(([^)]*)\)")
NON_KEY_JSON_KEYS = {"_forrás", "_megjegyzés", "_bizonytalan_tételek"}

# Human-confirmed picks -- checked against real biographical facts, not
# guessed. Keyed by the raw book string (each currently appears exactly
# once in composers_summary.json, so no cross-entry collision risk);
# short-circuits round1_search/narrowing entirely, so this also covers
# names round1 would report as "not found" due to a genuine spelling
# mismatch against composers.name/composer_alt_names (not just names
# left ambiguous by multiple real candidates).
CONFIRMED_PICKS = {
    "Couperin": "Q50186",              # François Couperin, per the Lexicon Français entry (1668-1733)
    "Albert (Eugen d')": "Q57178",     # Eugen d'Albert, studied under Hans Richter and Liszt (1864-1932)
    "Martin": "Q123910",               # Frank Martin, twelve-tone technique (1890-1974)
    "Landino": "Q311674",              # DB has "Francesco Landini" (i, not o) -- same person
    "Perotinus Magnus": "Q206275",     # DB has "Pérotin"/"Perotinus" with no "Magnus" epithet stored
    "Altnikol": "Q67366",              # DB has "Johann Christoph Altnickol" (extra c) -- same person
    "Gubajdulina": "Q165668",          # Sofia Gubaidulina (1931-2025), Hungarian-transliterated Russian name
    "Gnyeszin": "Q601425",             # Mikhail Gnessin (1883-1957) -- DB has "Gnessin" (double s)
    "Gyenyiszov": "Q275659",           # Edison Denisov (1929-1996), Moscow avant-garde group
    "Gyeszjatnyikov": "Q1986248",      # Leonid Desyatnikov (1955-)
    "Ribnyikov": "Q195773",            # Alexey Rybnikov (1945-), studied under Khachaturian
    "Schäffer": "Q465396",             # Bogusław Schaeffer (1929-2019) -- DB has German ae-transliteration
                                        # "Schaeffer", not umlaut-stripped "Schaffer" (strip_accents doesn't
                                        # do the ä->ae/ö->oe/ü->ue substitution, only drops combining marks)
    "Sztravinszkij": "Q7314",          # Igor Stravinsky -- DB's own hu label is "Igor Stravinsky" (untranslated),
                                        # "Sztravinszkij" belongs to his father Fyodor in our cache, see CLAUDE.md history
    "Tiscsenko": "Q893684",            # Boris Tishchenko (1939-2010)
    "Usztvolszkaja": "Q255300",        # Galina Ustvolskaya (1919-2006)
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def parse_entry(raw):
    """raw book string -> (surname_variants: list[str], given_hint: str|None)"""
    surnames = []
    given_hint = None
    for variant in (v.strip() for v in raw.split("|")):
        m = PAREN_RE.search(variant)
        if not m:
            surnames.append(variant)
            continue
        qualifier = m.group(1).strip()
        before = variant[: m.start()].strip()
        after = variant[m.end():].strip()
        bare = f"{before} {after}".strip()
        surnames.append(bare)
        if before and after:
            # epithet folded into the name, mid-string (Tinódi (Lantos)
            # Sebestyén) -- not a given name, try with and without it.
            surnames.append(f"{before} {qualifier} {after}".strip())
            surnames.append(f"{before} {qualifier}".strip())
        elif after:
            # leading parenthetical particle/prefix ("(De) Falla") -- also
            # try it fused onto the surname, but never as a bare surname
            # on its own (that's what "Albert (Eugen d')"'s "before qualifier"
            # variant would give for THIS case if treated like the Tinódi one:
            # a useless one-word "De" that matches almost anyone).
            surnames.append(f"{qualifier} {after}".strip())
        else:
            given_hint = given_hint or qualifier
    seen, uniq = set(), []
    for s in surnames:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq, given_hint


def word_match(haystack, needle):
    if not haystack or not needle:
        return False
    pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
    return re.search(pattern, haystack, re.IGNORECASE) is not None


def load_all(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, name, wikidata_id, birth_year FROM composers")
        composers = cur.fetchall()
        cur.execute("SELECT composer_id, language, name FROM composer_alt_names")
        alt_rows = cur.fetchall()
    alt_by_composer = {}
    for a in alt_rows:
        alt_by_composer.setdefault(a["composer_id"], []).append((a["language"], a["name"]))
    return composers, alt_by_composer


def candidates_for_variants(variants, composers, alt_by_composer, hu_only, stripped):
    vs = [strip_accents(v) for v in variants] if stripped else variants
    found = set()
    for c in composers:
        cname = strip_accents(c["name"]) if stripped else c["name"]
        if any(word_match(cname, v) for v in vs):
            found.add(c["id"])
            continue
        for lang, alt in alt_by_composer.get(c["id"], ()):
            if hu_only and lang != "hu":
                continue
            aname = strip_accents(alt) if stripped else alt
            if any(word_match(aname, v) for v in vs):
                found.add(c["id"])
                break
    return found


def round1_search(variants, composers, alt_by_composer):
    for hu_only in (True, False):
        for stripped in (False, True):
            ids = candidates_for_variants(variants, composers, alt_by_composer, hu_only, stripped)
            if ids:
                return ids
    return set()


def narrow_by_given_name(ids, given_hint, composers_by_id, alt_by_composer):
    if not given_hint or len(ids) <= 1:
        return ids
    hint_variants = [given_hint, strip_accents(given_hint)]
    narrowed = set()
    for cid in ids:
        c = composers_by_id[cid]
        names_to_check = [c["name"], strip_accents(c["name"])]
        names_to_check += [n for _lang, n in alt_by_composer.get(cid, ())]
        if any(word_match(n, h) for n in names_to_check for h in hint_variants):
            narrowed.add(cid)
    return narrowed or ids  # never narrow to zero


def narrow_by_era(ids, era_key, composers_by_id):
    if len(ids) <= 1 or era_key not in ERA_BIRTH_YEAR_RANGE:
        return ids
    lo, hi = ERA_BIRTH_YEAR_RANGE[era_key]
    narrowed = set()
    for cid in ids:
        by = composers_by_id[cid]["birth_year"]
        if by is None:
            continue
        if (lo is None or by >= lo) and (hi is None or by <= hi):
            narrowed.add(cid)
    return narrowed or ids  # never narrow to zero


def resolve_name(raw, era_key, composers, composers_by_id, composers_by_qid, alt_by_composer):
    confirmed_qid = CONFIRMED_PICKS.get(raw)
    if confirmed_qid:
        cid = composers_by_qid[confirmed_qid]
        return [raw, confirmed_qid, cid]
    variants, given_hint = parse_entry(raw)
    ids = round1_search(variants, composers, alt_by_composer)
    if not ids:
        return [raw, "", -1]
    ids = narrow_by_given_name(ids, given_hint, composers_by_id, alt_by_composer)
    ids = narrow_by_era(ids, era_key, composers_by_id)
    if len(ids) == 1:
        cid = next(iter(ids))
        return [raw, composers_by_id[cid]["wikidata_id"] or "", cid]
    id_list = sorted(ids)
    qids = "/".join(composers_by_id[cid]["wikidata_id"] for cid in id_list if composers_by_id[cid]["wikidata_id"])
    return [raw, qids, id_list[0]]


def walk(node, era_key, composers, composers_by_id, composers_by_qid, alt_by_composer):
    """node is either a {nationality/subperiod: [names]} dict or a flat
    list of name strings -- era_key is fixed for the whole subtree, set
    once by the caller from the top-level era key."""
    if isinstance(node, dict):
        return {k: walk(v, era_key, composers, composers_by_id, composers_by_qid, alt_by_composer) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve_name(n, era_key, composers, composers_by_id, composers_by_qid, alt_by_composer) for n in node]
    return node


def main():
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    conn = psycopg2.connect()
    try:
        composers, alt_by_composer = load_all(conn)
    finally:
        conn.close()
    composers_by_id = {c["id"]: c for c in composers}
    composers_by_qid = {c["wikidata_id"]: c["id"] for c in composers if c["wikidata_id"]}

    resolved = {}
    not_found = 0
    ambiguous = 0
    unique = 0
    for top_key, top_val in data.items():
        if top_key in NON_KEY_JSON_KEYS:
            resolved[top_key] = top_val
            continue
        resolved[top_key] = walk(top_val, top_key, composers, composers_by_id, composers_by_qid, alt_by_composer)

    def count(node):
        nonlocal not_found, ambiguous, unique
        if isinstance(node, list) and len(node) == 3 and isinstance(node[0], str) and isinstance(node[2], int):
            if node[2] == -1:
                not_found += 1
            elif "/" in node[1]:
                ambiguous += 1
            else:
                unique += 1
        elif isinstance(node, dict):
            for k, v in node.items():
                if k not in NON_KEY_JSON_KEYS:
                    count(v)
        elif isinstance(node, list):
            for v in node:
                count(v)

    for k, v in resolved.items():
        if k not in NON_KEY_JSON_KEYS:
            count(v)

    OUTPUT_FILE.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")
    print(f"unique: {unique}, ambiguous: {ambiguous}, not found: {not_found}")


if __name__ == "__main__":
    main()

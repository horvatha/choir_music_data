"""Parse composers.nationality (raw, free-text, ~375 distinct strings) into
the nationalities / composer_nationalities N:M tables.

The raw field mixes wildly inconsistent conventions: plain single words
("German"), "-born" compounds ("German-born Canadian", "American
(German-born)"), plain compounds with no birth marker ("Greek-American"),
comma/semicolon/slash-separated lists ("Russian, British, Israeli"),
combining-form identities that are their own thing rather than two
nationalities ("Franco-Flemish", "Austro-Hungarian"), multi-word single
nationalities that must not be split ("South African", "New Zealand"), and
some outright garbled entries ("Western Europeanprobably French or German").

Only an explicit "-born" marker sets is_origin_only = TRUE on that
token; everything else is FALSE, including both sides of an unmarked
compound like "Greek-American" -- the source doesn't say which came first,
so this doesn't guess. Strings this parser doesn't confidently recognize
fall back to being inserted as a single nationality equal to the whole raw
string, so nothing is silently dropped -- run with --report to see which
raw strings hit that fallback before deciding whether to special-case them.
"""
import re
import sys

import psycopg2

from adapters.json_cache import load_cache
from domain.nationalities import predict_need_to_check, suggest_nationality_from_birthplace
from fetch_wikidata_relationships import OUTPUT_FILE

# Combining-form prefixes: never a nationality on their own, and a compound
# starting with one names a specific identity (e.g. the Franco-Flemish
# School) rather than "has both nationalities" -- kept whole, not split.
COMBINING_PREFIXES = {"anglo", "franco", "austro", "sino", "italo", "judeo", "luso"}

# Multi-word nationalities that must not be split on whitespace or "and".
PROTECTED_PHRASES = {
    "south african", "new zealand", "new zealander", "costa rican",
    "puerto rican", "sri lankan", "northern irish", "south korean",
    "hong kong", "bosnia and herzegovina", "western european",
    "finland-swedish",
}

# A parenthetical hedge on an already-vague outer classification (e.g.
# "Western European (probably French or German)") is not a second
# nationality to tag separately -- unlike "French or Flemish" (the
# *entire* field being a genuine either/or, which does get split into two
# tags, see CLAUDE.md), this is a low-confidence guess about which country
# within an already-uncertain broader claim, so the guess is dropped and
# only the outer (still uncertain, but at least sourced-as-stated)
# classification is kept.
HEDGE_RE = re.compile(r"^(?:probably|perhaps|possibly)\s+", re.IGNORECASE)

BORN_INNER_RE = re.compile(r"^(.+?)[\s-]born$", re.IGNORECASE)
BORN_PREFIX_RE = re.compile(r"^born[\s-](.+)$", re.IGNORECASE)
BORN_SPLIT_RE = re.compile(r"^(.+?)[\s-]born,?\s*(.+)$", re.IGNORECASE)
PAREN_RE = re.compile(r"^(.+?)\s*\((.+)\)$")
LIST_SEP_RE = re.compile(r"\s*(?:,|;|/|\band\b)\s*", re.IGNORECASE)

# Some raw nationality strings use the country name or an alternate demonym
# instead of the standard adjective; canonicalize (case-insensitive) so they
# don't end up as separate nationalities rows. "Kosovar" was picked over
# "Kosovan"/"Kosovo" as the more common English demonym (matches Wikipedia's
# own usage, e.g. "Kosovar Albanians").
CANONICAL_NAMES = {
    "georgia": "Georgian",
    "new zealand": "New Zealander",
    "kosovo": "Kosovar",
    "kosovan": "Kosovar",
    # A language-region distinction within one civic nationality (Swedish-
    # speaking Finns) -- same non-split treatment as Switzerland's German/
    # French/Italian-speaking regions (see CLAUDE.md), so this maps to the
    # plain nationality rather than getting its own tag or being word-split
    # into bogus "Finland" + "Swedish" tags.
    "finland-swedish": "Finnish",
}


def _clean(token: str) -> str:
    token = token.strip().rstrip("?").strip()
    return CANONICAL_NAMES.get(token.lower(), token)


def _is_protected(text: str) -> bool:
    return text.strip().lower() in PROTECTED_PHRASES


def _starts_with_combining_prefix(text: str) -> bool:
    first = text.split("-", 1)[0].strip().lower()
    return first in COMBINING_PREFIXES


def _split_list(text: str) -> list[str]:
    """Split on , ; / and 'and', but never inside a protected phrase."""
    if _is_protected(text):
        return [text]
    parts = [p for p in LIST_SEP_RE.split(text) if p.strip()]
    return parts if len(parts) > 1 else [text]


# "and" is handled earlier, by _split_list (LIST_SEP_RE) -- it means the
# composer genuinely has both. "or" means the source is unsure which single
# nationality applies; OR_RE below handles that case explicitly (split into
# both, flagged need_to_check), so by the time _split_plain_compound sees a
# leftover "or"/"and" it's just a safety net against blind whitespace-
# splitting a phrase neither pattern caught.
STOPWORDS = {"or", "and"}

# "X or Y" -- e.g. "English or French", "French or Flemish" -- a genuine
# either/or ambiguity in the source (see CLAUDE.md's "Genuine either/or
# ambiguity" rule): split into both, need_to_check = TRUE on each, since
# nobody has confirmed which one actually applies. Distinct from a
# combining-form/protected phrase (checked before this runs) and from the
# HEDGE_RE parenthetical case ("Western European (probably French or
# German)"), where the outer classification is the confident part and the
# "or" guess is just a dropped hedge, not a real split.
OR_RE = re.compile(r"^([A-Za-z][A-Za-z\s]*?)\s+or\s+([A-Za-z][A-Za-z\s]*)$", re.IGNORECASE)


def _split_plain_compound(text: str) -> list[str]:
    """Split a single token further: on '-' (unless protected/combining),
    then on whitespace for short (2-3 word) leftovers."""
    text = text.strip()
    if _is_protected(text) or _starts_with_combining_prefix(text):
        return [text]
    if "-" in text:
        parts = [p.strip() for p in text.split("-") if p.strip()]
        if len(parts) > 1:
            return parts
    words = text.split()
    if 2 <= len(words) <= 3 and not any(w.lower() in STOPWORDS for w in words):
        return words
    return [text]


def parse_nationality(raw: str) -> list[tuple[str, bool, bool]]:
    """Return [(nationality_name, is_origin_only, need_to_check), ...] for
    one composers.nationality value."""
    text = raw.strip()
    if not text:
        return []

    # "Y (X-born)" / "Y (X)" -- unwrap only when the parenthetical content
    # is plausibly a nationality (letters/hyphens/spaces only), not e.g.
    # "Arles/Burgundy".
    m = PAREN_RE.match(text)
    if m:
        if re.fullmatch(r"[A-Za-z\s-]+", m.group(2)):
            outer, inner = m.group(1).strip(), m.group(2).strip()
            inner_born = BORN_INNER_RE.match(inner)
            if inner_born:
                return [(_clean(outer), False, False), (_clean(inner_born.group(1)), True, False)]
            # "Y (born X)" -- born marker at the *start* of the
            # parenthetical (as opposed to "Y (X-born)", handled above) --
            # e.g. "Australian (born English)".
            born_prefix = BORN_PREFIX_RE.match(inner)
            if born_prefix:
                return [(_clean(outer), False, False), (_clean(born_prefix.group(1)), True, False)]
            if HEDGE_RE.match(inner):
                return parse_nationality(outer)
            return parse_nationality(outer) + parse_nationality(inner)
        # Parenthetical content doesn't look like a nationality (e.g. place
        # names, slashes) -- don't guess, keep the whole string as one token.
        return [(_clean(text), False, False)]

    if _starts_with_combining_prefix(text) or _is_protected(text):
        return [(_clean(text), False, False)]

    # Split on , ; / and 'and' *before* checking for a bare "X-born" marker
    # below -- otherwise "German, Swiss; Scottish-born" matches "-born" as
    # anchored to the end of the *whole* string and swallows all three
    # nationalities into one birth-marked blob instead of splitting first.
    list_parts = _split_list(text)
    if len(list_parts) > 1:
        result = []
        for part in list_parts:
            result.extend(parse_nationality(part))
        return result

    # "X or Y" -- genuine either/or ambiguity, checked before the "-born"
    # patterns below since neither of those apply to a bare "or" field.
    or_match = OR_RE.match(text)
    if or_match:
        return [(_clean(or_match.group(1)), False, True), (_clean(or_match.group(2)), False, True)]

    # "X-born Y" / "X born Y" / "X-bornY" / "X-born, Y"
    m = BORN_SPLIT_RE.match(text)
    if m:
        birth_part, rest = m.groups()
        return [(_clean(birth_part), True, False)] + [
            (_clean(token), False, False) for token in _split_plain_compound(rest.strip())
        ]

    # "X-born" / "X born" with nothing following -- the birth marker for a
    # nationality that was already split off a surrounding list, e.g. the
    # "Scottish-born" in "German, Swiss; Scottish-born".
    m = BORN_INNER_RE.match(text)
    if m:
        return [(_clean(m.group(1)), True, False)]

    return [(_clean(token), False, False) for token in _split_plain_compound(text)]


FETCH_NATIONALITIES_SQL = """
    SELECT id, nationality, wikidata_id FROM composers
    WHERE nationality IS NOT NULL AND nationality != ''
"""

UPSERT_NATIONALITY_SQL = """
    INSERT INTO nationalities (name) VALUES (%s)
    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

LINK_NATIONALITY_SQL = """
    INSERT INTO composer_nationalities (composer_id, nationality_id, is_origin_only, need_to_check)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (composer_id, nationality_id) DO UPDATE
        SET is_origin_only = composer_nationalities.is_origin_only OR EXCLUDED.is_origin_only,
            need_to_check = composer_nationalities.need_to_check OR EXCLUDED.need_to_check
"""

# Composers with no nationality at all after the CSV pass above (blank
# composers.nationality, so FETCH_NATIONALITIES_SQL never even saw them)
# -- candidates for domain.nationalities.suggest_nationality_from_
# birthplace, keyed off their already-resolved birth country rather than
# a citizenship claim. See that module's docstring for the restrictions
# (MIN_BIRTHPLACE_SUGGESTION_YEAR, VOLATILE_BIRTH_COUNTRIES) and
# reports/birthplace_nationality_suggestions.md (gitignored) for the
# research behind them.
FETCH_BIRTHPLACE_CANDIDATES_SQL = """
    SELECT c.id, c.birth_year, co.wikidata_id
    FROM composers c
    JOIN place_periods pp ON pp.id = c.birth_place_id
    JOIN countries co ON co.id = pp.country_id
    WHERE NOT EXISTS (
        SELECT 1 FROM composer_nationalities cn WHERE cn.composer_id = c.id
    )
"""


def report():
    """Print, for every distinct raw nationality string, how it parses --
    so fallback (unrecognized, kept-whole) cases can be reviewed before
    loading."""
    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT nationality, count(*) FROM composers
                WHERE nationality IS NOT NULL AND nationality != ''
                GROUP BY nationality ORDER BY nationality
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    fallback_count = 0
    for raw, count in rows:
        parsed = parse_nationality(raw)
        is_fallback = len(parsed) == 1 and parsed[0][0].lower() == _clean(raw).lower() and (
            "-" in raw or "," in raw or ";" in raw or "/" in raw or " and " in raw.lower()
            or " " in _clean(raw)
        ) and not _starts_with_combining_prefix(raw) and not _is_protected(raw)
        marker = "  [fallback: kept whole, had separators but didn't split]" if is_fallback else ""
        if is_fallback:
            fallback_count += 1
        tokens = ", ".join(
            f"{name}{'*' if born else ''}{'?' if check else ''}" for name, born, check in parsed
        )
        print(f"{raw!r:55} (n={count:4}) -> {tokens}{marker}")
    print(f"\n{len(rows)} distinct raw strings, {fallback_count} fell back to a single kept-whole token")


def load():
    """Fully rebuilds nationalities/composer_nationalities from
    composers.nationality. Not incremental -- truncates first, so reruns
    after a parsing/canonicalization change don't leave stale rows behind
    (e.g. an old "Georgia" nationality orphaned after it's renamed to
    "Georgian").

    need_to_check is the OR of two independent sources: parse_nationality's
    own either/or-field detection (a bare "X or Y" in the raw text), and
    domain.nationalities.predict_need_to_check (a citizenship-claim-only
    bulk assignment with no independent verification -- see that module's
    docstring for the full history of why this needs predicting rather
    than just hardcoding, same TRUNCATE-wipes-hand-patch lesson as
    load_tags.py/load_place_period_names.py elsewhere in this repo).

    Three sources, in order, same priority CSV data has always had over
    a guess: (1) composers.nationality free text, (2) citizenship-claim
    prediction layered onto (1)'s need_to_check, (3) only for composers
    (1) left with *no* nationality row at all, domain.nationalities.
    suggest_nationality_from_birthplace -- always need_to_check=TRUE,
    since a birthplace is explicitly a guess, never asserted as fact."""
    data = load_cache(OUTPUT_FILE)
    entries = data.get("composers", {})

    conn = psycopg2.connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_nationalities, nationalities RESTART IDENTITY CASCADE")
                cur.execute(FETCH_NATIONALITIES_SQL)
                rows = cur.fetchall()
                for composer_id, raw, wikidata_id in rows:
                    citizenship_qids = entries.get(str(composer_id), {}).get("attributes", {}).get("citizenship", [])
                    for name, is_origin_only, need_to_check in parse_nationality(raw):
                        if not name:
                            continue
                        need_to_check = need_to_check or predict_need_to_check(
                            composer_id, wikidata_id, name, citizenship_qids
                        )
                        cur.execute(UPSERT_NATIONALITY_SQL, (name,))
                        nationality_id = cur.fetchone()[0]
                        cur.execute(LINK_NATIONALITY_SQL, (composer_id, nationality_id, is_origin_only, need_to_check))

                cur.execute(FETCH_BIRTHPLACE_CANDIDATES_SQL)
                birthplace_rows = cur.fetchall()
                birthplace_suggested = 0
                for composer_id, birth_year, country_wikidata_id in birthplace_rows:
                    suggested_name = suggest_nationality_from_birthplace(birth_year, country_wikidata_id)
                    if not suggested_name:
                        continue
                    cur.execute(UPSERT_NATIONALITY_SQL, (suggested_name,))
                    nationality_id = cur.fetchone()[0]
                    cur.execute(LINK_NATIONALITY_SQL, (composer_id, nationality_id, False, True))
                    birthplace_suggested += 1
    finally:
        conn.close()
    print(f"Processed {len(rows)} composers with a nationality."
          f" Suggested {birthplace_suggested} more from birthplace"
          f" ({len(birthplace_rows)} candidates with no other nationality).")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        load()
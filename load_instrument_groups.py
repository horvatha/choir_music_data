"""Define the instrument_groups taxonomy and assign every instrument to
its group, from the Hornbostel-Sachs codes and P279 ancestor sets
fetch_instrument_classification.py cached into wikidata_relationships.json.

The taxonomy itself (GROUPS below) is hand-curated, not derived -- see
schema.sql's comment on instrument_groups for why. Two levels: a small set
of top-level families, two of which (winds, strings) have subfamilies.
Percussion/keyboards/electronic/other stay one level -- not every
instrument needs a subfamily.

classify() below is the interesting part -- see its docstring for the
actual per-instrument logic (Hornbostel-Sachs digits as the primary
signal, a P279-based keyboard override layered on top, "other" as the
explicit fallback when nothing resolves).

Usage:
    python3 load_instrument_groups.py
"""

import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE, TARGET_LANGUAGES, api_get

# (key, wikidata_id | None, parent_key | None, display_order). wikidata_id
# is None only for "other", which has no single Wikidata concept -- it's
# this repo's own catch-all, not a Wikidata category. display_order ranks
# among siblings (other top-level groups, or other subfamilies under the
# same parent) -- "other" is deliberately the highest top-level order so
# it always sorts last, per the app's display requirement.
GROUPS = [
    ("winds", "Q173453", None, 0),
    ("strings", "Q1798603", None, 1),
    ("percussion", "Q133163", None, 2),
    ("keyboards", "Q52954", None, 3),
    ("electronic", "Q1327500", None, 4),
    ("other", None, None, 5),
    ("brass", "Q180744", "winds", 0),
    ("woodwind", "Q181247", "winds", 1),
    ("bowed_strings", "Q192096", "strings", 0),
    ("plucked_strings", "Q230262", "strings", 1),
]

# "other" has no Wikidata item to pull a label from -- hand-typed for the
# languages this repo actually has UI/data coverage for today (see
# CLAUDE.md's "Target languages for translated names"; more can be filled
# in later the same way any other translation gap gets patched).
OTHER_GROUP_NAMES = {
    "en": "Other",
    "hu": "Egyéb",
}

KEYBOARD_QID = "Q52954"
BOWED_STRING_QID = "Q192096"
PLUCKED_STRING_QID = "Q230262"

UPSERT_GROUP_SQL = """
    INSERT INTO instrument_groups (name, wikidata_id, parent_group_id, display_order)
    VALUES (%(name)s, %(wikidata_id)s, %(parent_group_id)s, %(display_order)s)
    ON CONFLICT (wikidata_id) DO UPDATE
        SET name = EXCLUDED.name, parent_group_id = EXCLUDED.parent_group_id,
            display_order = EXCLUDED.display_order
    RETURNING id
"""

# "other" has a NULL wikidata_id, so it can't use the ON CONFLICT
# (wikidata_id) upsert above -- NULL never conflicts with NULL under a
# UNIQUE constraint, so "ON CONFLICT (wikidata_id) DO ..." silently
# wouldn't fire and every rerun would insert a fresh duplicate "other"
# row. Selected-then-inserted by hand instead (see load() below), the
# only group this applies to.
FIND_OTHER_GROUP_SQL = "SELECT id FROM instrument_groups WHERE wikidata_id IS NULL AND parent_group_id IS NULL"
INSERT_OTHER_GROUP_SQL = """
    INSERT INTO instrument_groups (name, wikidata_id, parent_group_id, display_order)
    VALUES (%s, NULL, NULL, %s) RETURNING id
"""
UPDATE_OTHER_GROUP_ORDER_SQL = "UPDATE instrument_groups SET display_order = %s WHERE id = %s"

UPSERT_GROUP_NAME_SQL = """
    INSERT INTO instrument_group_names (group_id, language, name)
    VALUES (%(group_id)s, %(language)s, %(name)s)
    ON CONFLICT (group_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def classify(hs_code, ancestor_qids):
    """(group_key, subfamily_key | None) for one instrument, given its
    Hornbostel-Sachs code (may be None) and P279 ancestor QID set.

    Keyboard is checked first and overrides everything else -- it's a
    "how it's played" category, not a "how it makes sound" one, so it
    can't be read off the Hornbostel-Sachs code at all (piano is a struck
    chordophone, organ an aerophone, by H-S's own logic).

    Otherwise, the Hornbostel-Sachs first digit gives the top-level
    family directly: 1 (idiophone) and 2 (membranophone) both collapse to
    "percussion" -- meaningful to an organologist, but to a listener a
    struck idiophone (xylophone) and a struck membranophone (timpani) are
    both just "percussion". 3 (chordophone) is "strings", 4 (aerophone)
    is "winds", 5 (electrophone) is "electronic".

    For winds specifically, the first three digits split further: 421
    (edge-blown) and 422 (reed) are enclosed-air-column aerophones proper
    -- "woodwind" -- while 423 (lip-vibrated) is "brass". Anything else
    under aerophone (e.g. 41x, free-reed instruments like accordion/
    harmonica) doesn't cleanly fit either and is left at "winds" with no
    subfamily rather than guessed at.

    For strings, Hornbostel-Sachs' own digits don't cleanly separate
    "bowed" from "plucked" the way they do woodwind/brass (that split is
    encoded in an extended dash-suffix convention this repo isn't
    confident parsing correctly -- unlike the P17/P1448-style claims used
    elsewhere, the dash-suffix meanings aren't consistently documented
    enough to trust without a reference this repo doesn't have), so this
    reuses the same P279-ancestor-membership approach as the keyboard
    check instead: Q192096 ("bowed string instrument") or Q230262
    ("plucked string instrument") anywhere in the ancestor set. Checked
    unconditionally, before the Hornbostel-Sachs code is even looked at --
    NOT nested under "first == '3'" -- because several real instruments
    (e.g. "viola da braccio", "electric viola") have no Hornbostel-Sachs
    code at all but do have Q192096 in their ancestor set; gating this
    check on an H-S code existing first would silently drop them to
    "other" despite the ancestor data already answering the question. A
    struck string instrument that's neither bowed nor plucked (e.g. a
    hammered dulcimer) or one where the ancestor walk didn't reach either
    QID within MAX_DEPTH still needs the Hornbostel-Sachs digit check
    below to even land in "strings" at all, though.

    No Hornbostel-Sachs code, no keyboard/bowed/plucked ancestor match ->
    "other".
    """
    if KEYBOARD_QID in ancestor_qids:
        return "keyboards", None
    if BOWED_STRING_QID in ancestor_qids:
        return "strings", "bowed_strings"
    if PLUCKED_STRING_QID in ancestor_qids:
        return "strings", "plucked_strings"
    if not hs_code:
        return "other", None
    first = hs_code[0]
    if first in ("1", "2"):
        return "percussion", None
    if first == "3":
        return "strings", None
    if first == "4":
        prefix3 = hs_code[:3]
        if prefix3 in ("421", "422"):
            return "winds", "woodwind"
        if prefix3 == "423":
            return "winds", "brass"
        return "winds", None
    if first == "5":
        return "electronic", None
    return "other", None


def load():
    data = load_cache(OUTPUT_FILE)
    hs_codes = data.get("instrument_hornbostel_sachs", {})
    ancestors = data.get("instrument_ancestors", {})

    group_qids = [wikidata_id for _key, wikidata_id, _parent, _order in GROUPS if wikidata_id]
    print(f"Fetching group names in {len(TARGET_LANGUAGES)} languages for {len(group_qids)} groups...")
    result = api_get(
        "https://www.wikidata.org/w/api.php",
        {"action": "wbgetentities", "format": "json", "ids": "|".join(group_qids),
         "props": "labels", "languages": "|".join(TARGET_LANGUAGES)},
    )
    group_labels = {
        qid: {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
        for qid, entity in result.get("entities", {}).items()
    }

    conn = psycopg2.connect()
    updated = 0
    try:
        with conn:
            with conn.cursor() as cur:
                group_id_by_key = {}
                # Two passes: top-level groups first (parent_group_id
                # NULL), then subfamilies, since a subfamily's row needs
                # its parent's id to already exist.
                for key, wikidata_id, parent_key, display_order in GROUPS:
                    if parent_key is not None:
                        continue
                    if wikidata_id is None:
                        cur.execute(FIND_OTHER_GROUP_SQL)
                        row = cur.fetchone()
                        if row is None:
                            cur.execute(INSERT_OTHER_GROUP_SQL, ("other", display_order))
                            row = cur.fetchone()
                        else:
                            cur.execute(UPDATE_OTHER_GROUP_ORDER_SQL, (display_order, row[0]))
                    else:
                        cur.execute(UPSERT_GROUP_SQL, {
                            "name": group_labels.get(wikidata_id, {}).get("en", key),
                            "wikidata_id": wikidata_id, "parent_group_id": None,
                            "display_order": display_order,
                        })
                        row = cur.fetchone()
                    group_id_by_key[key] = row[0]

                for key, wikidata_id, parent_key, display_order in GROUPS:
                    if parent_key is None:
                        continue
                    cur.execute(UPSERT_GROUP_SQL, {
                        "name": group_labels.get(wikidata_id, {}).get("en", key),
                        "wikidata_id": wikidata_id, "parent_group_id": group_id_by_key[parent_key],
                        "display_order": display_order,
                    })
                    group_id_by_key[key] = cur.fetchone()[0]

                for key, wikidata_id, _parent, _order in GROUPS:
                    group_id = group_id_by_key[key]
                    names = dict(OTHER_GROUP_NAMES) if wikidata_id is None else group_labels.get(wikidata_id, {})
                    for language, name in names.items():
                        if language not in TARGET_LANGUAGES and language not in OTHER_GROUP_NAMES:
                            continue
                        cur.execute(UPSERT_GROUP_NAME_SQL, {"group_id": group_id, "language": language, "name": name})

                cur.execute("SELECT id, wikidata_id FROM instruments WHERE wikidata_id IS NOT NULL")
                for instrument_id, wikidata_id in cur.fetchall():
                    group_key, subfamily_key = classify(
                        hs_codes.get(wikidata_id), set(ancestors.get(wikidata_id, []))
                    )
                    leaf_key = subfamily_key or group_key
                    cur.execute(
                        "UPDATE instruments SET group_id = %s WHERE id = %s",
                        (group_id_by_key[leaf_key], instrument_id),
                    )
                    updated += 1
    finally:
        conn.close()
    print(f"Assigned a group to {updated} instruments.")


if __name__ == "__main__":
    load()
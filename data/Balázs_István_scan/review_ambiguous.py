"""Interactive review of composers_summary.json entries that
resolve_composers.py couldn't place uniquely -- walks every ambiguous
name (pure alphabetical order, era/nationality shown for context, "not
found" entries with zero candidates are skipped since there's nothing
to pick from), shows the real DB candidates, and lets you either accept
this script's suggested pick (SUGGESTED_PICKS in resolve_composers.py)
with Enter, or type a number to choose a different one.

Picks are written to confirmed_picks_interactive.json as you go (one
write per decision, so nothing is lost if you quit partway through) --
resolve_composers.py loads that file on top of its own hardcoded
CONFIRMED_PICKS on every run, so a rerun after this picks the choices
up automatically.

Usage:
    python3 review_ambiguous.py
    (Enter = accept suggestion; a number = pick that candidate;
     s = skip this one; q = quit and save what's done so far)
"""
import json

import psycopg2
import psycopg2.extras

from resolve_composers import (
    CONFIRMED_PICKS,
    CONFIRMED_PICKS_FILE,
    INPUT_FILE,
    NON_KEY_JSON_KEYS,
    SUGGESTED_PICKS,
    hungarian_sort_key,
    load_all,
    walk,
)


def collect_ambiguous(data, composers, composers_by_id, composers_by_qid, alt_by_composer):
    rows = []

    def visit(node, era, sub):
        if isinstance(node, dict):
            for k, v in node.items():
                visit(v, era, k)
        elif isinstance(node, list):
            if node and isinstance(node[0], str) and len(node) == 3 and isinstance(node[2], int):
                name, qid, cid = node
                if qid and "/" in qid:
                    rows.append((era, sub, name, qid))
            else:
                for v in node:
                    visit(v, era, sub)

    for top_key, top_val in data.items():
        if top_key in NON_KEY_JSON_KEYS:
            continue
        resolved_val = walk(top_val, top_key, composers, composers_by_id, composers_by_qid, alt_by_composer)
        visit(resolved_val, top_key, "")
    return rows


def main():
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    conn = psycopg2.connect()
    try:
        composers, alt_by_composer = load_all(conn)
    finally:
        conn.close()
    composers_by_id = {c["id"]: c for c in composers}
    composers_by_qid = {c["wikidata_id"]: c["id"] for c in composers if c["wikidata_id"]}

    rows = collect_ambiguous(data, composers, composers_by_id, composers_by_qid, alt_by_composer)
    rows.sort(key=lambda r: hungarian_sort_key(r[2]))  # pure alphabetical, like a lexicon

    interactive_picks = dict(json.loads(CONFIRMED_PICKS_FILE.read_text(encoding="utf-8"))) \
        if CONFIRMED_PICKS_FILE.exists() else {}

    decided = 0
    skipped = 0
    for era, sub, name, qid in rows:
        if name in CONFIRMED_PICKS:
            continue  # already resolved (hardcoded or an earlier interactive session)
        candidate_ids = [composers_by_qid[q] for q in qid.split("/")]
        print(f"\n{name}  [{era} / {sub}]" if sub else f"\n{name}  [{era}]")
        suggested_qid = SUGGESTED_PICKS.get(name)
        for i, cid in enumerate(candidate_ids, start=1):
            c = composers_by_id[cid]
            marker = " *" if c["wikidata_id"] == suggested_qid else ""
            by = c["birth_year"] if c["birth_year"] is not None else "?"
            dy = c["death_year"] if c["death_year"] is not None else ""
            print(f"  {i}) {c['name']} ({by}-{dy}) {c['wikidata_id']}{marker}")
        if suggested_qid:
            prompt = "Enter=javaslat elfogadása (*), szám=másik, s=kihagyás, q=kilépés: "
        else:
            prompt = "nincs javaslat -- szám a választáshoz, Enter/s=kihagyás, q=kilépés: "
        choice = input(prompt).strip()

        if choice.lower() == "q":
            break
        if choice.lower() == "s" or (choice == "" and not suggested_qid):
            skipped += 1
            continue
        if choice == "" and suggested_qid:
            picked_qid = suggested_qid
        elif choice.isdigit() and 1 <= int(choice) <= len(candidate_ids):
            picked_qid = composers_by_id[candidate_ids[int(choice) - 1]]["wikidata_id"]
        else:
            print("  (nem értelmezhető válasz, kihagyva)")
            skipped += 1
            continue

        interactive_picks[name] = picked_qid
        CONFIRMED_PICKS_FILE.write_text(
            json.dumps(interactive_picks, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        decided += 1
        print(f"  -> mentve: {picked_qid}")

    print(f"\n{decided} eldöntve, {skipped} kihagyva ebben a menetben.")
    print(f"Futtasd újra: python3 resolve_composers.py")


if __name__ == "__main__":
    main()

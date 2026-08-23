"""Report candidates fetched via fetch_missing_composers_from_relations.py/
fetch_candidate_people.py who *do* have "composer" (Q36834) among their
Wikidata occupations (P106) but were still excluded by
load_missing_composers.py's description-substring filter -- i.e. people
Wikidata itself calls a composer among their occupations, just not as
their defining one, so they won't end up in the composers table as things
stand.

Deliberately narrower than "every not-loaded candidate": round 2's
fetch_candidate_people.py stored *everyone* it found regardless of
occupation (family members, non-composer relations, ...), so most of the
3763 not-yet-loaded entries were never composers at all by occupation --
those are excluded here, not just the ones whose description happened to
omit the word. Round 1's candidates were already pre-filtered by a P106
check when missing_composers_from_relations.csv was built, so re-checking
them here is redundant but harmless (confirms the same set).

Occupation isn't already in wikidata_relationships.json (P106 was never
part of RELATIONSHIP_PROPS/ATTRIBUTE_PROPS -- the round-1 P106 check that
built missing_composers_from_relations.csv was a one-off, not persisted),
so this fetches it fresh via wbgetclaims for every not-loaded candidate,
batched 50/call, and caches the result under data["occupations"] (QID ->
list of occupation QIDs) so a rerun only fetches newly-added candidates.

Doesn't touch the DB at all -- any entry still keyed "new:<qid>" in
wikidata_relationships.json is, by construction, not loaded (loading it
via load_missing_composers.py re-keys it to a numeric composer_id), so
the cache alone is enough to compute this.

Columns: name, wikidata_id, en description, en Wikipedia article URL (from
cached sitelinks, blank if no en article).

Usage:
    python3 report_unloaded_candidates.py
"""
import csv

from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import api_get
from fetch_wikidata_relationships import OUTPUT_FILE

OUTPUT_CSV = "unloaded_candidates.csv"
COMPOSER_QID = "Q36834"


def wikipedia_url(entry):
    title = entry.get("sitelinks", {}).get("en")
    if not title:
        return ""
    return "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")


def fetch_occupations(qids):
    """{qid: [occupation_qid, ...]} for every qid, via P106 claims."""
    result = {}
    qids = list(qids)
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "claims"},
        )
        for qid, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {}).get("P106", [])
            result[qid] = [
                c["mainsnak"]["datavalue"]["value"]["id"]
                for c in claims
                if c.get("mainsnak", {}).get("datavalue", {}).get("type") == "wikibase-entityid"
            ]
        print(f"  {min(i + 50, len(qids))}/{len(qids)}...")
    return result


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data["composers"]

    # A handful of "new:" entries have no resolved qid at all (e.g.
    # "new:Ilayaraja", keyed by name because the original fetch never
    # found a QID for them) -- can't look up P106 for those, so drop them
    # rather than crash the batch join.
    not_loaded = {
        key: entry for key, entry in entries.items()
        if key.startswith("new:") and entry.get("qid")
    }

    occupations = data.setdefault("occupations", {})
    todo = [entry["qid"] for entry in not_loaded.values() if entry["qid"] not in occupations]
    if todo:
        print(f"fetching occupations for {len(todo)} not-yet-checked candidates...")
        occupations.update(fetch_occupations(todo))
        save_cache(OUTPUT_FILE, data)

    rows = []
    for entry in not_loaded.values():
        qid = entry["qid"]
        if COMPOSER_QID not in occupations.get(qid, []):
            continue
        description = entry.get("descriptions", {}).get("en", "")
        if "composer" in description.lower():
            # Shouldn't happen (would mean promotion missed a loaded
            # composer) -- exclude defensively rather than mis-report it.
            continue
        rows.append({
            "name": entry.get("name", ""),
            "wikidata_id": qid,
            "description": description,
            "wikipedia_en": wikipedia_url(entry),
        })

    rows.sort(key=lambda r: r["name"].lower())

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "wikidata_id", "description", "wikipedia_en"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} not-loaded candidates (with 'composer' among P106 occupations) written to {OUTPUT_CSV}.")


if __name__ == "__main__":
    main()

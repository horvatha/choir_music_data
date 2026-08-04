"""Fetch full Wikidata data for the candidates in
missing_composers_from_relations.csv -- people who showed up as an
unlinked teacher or notable-student of a composer already in the DB, and
were confirmed to have "composer" among their Wikidata occupations (see
chat: /tmp scratchpad's check_missing_composers.py). None of them are in
the composers table yet.

Deliberately does *no* filtering at fetch time (e.g. no popular-vs-
classical exclusion like fetch_new_21st_century_wikidata.py has) -- the
whole point of fetching everything up front is to let filter criteria
(primary occupation vs. composer-as-minor-occupation, genre, era, ...) get
worked out afterward against the cache, with zero further API calls,
rather than deciding the rule before the data exists to check it against.

Fetches every language Wikidata has a label *and* description in (not
restricted to TARGET_LANGUAGES/BASE_LABEL_LANGUAGES the way the rest of
this pipeline is) -- descriptions specifically to support the
primary-occupation filtering pass, labels because "which languages to
keep" is exactly the kind of decision this fetch is meant to defer.

Entries are keyed "new:<qid>" in wikidata_relationships.json's
"composers" dict, same convention as fetch_new_21st_century_wikidata.py
(composer_id doesn't exist yet) -- a future loader step decides whether/
how each one gets loaded.

Usage:
    python3 fetch_missing_composers_from_relations.py
"""
import csv
import json

from fetch_wikidata_relationships import (
    OUTPUT_FILE, api_get, extract_attributes, extract_dates,
    extract_relationships, extract_sitelinks,
)

INPUT_CSV = "missing_composers_from_relations.csv"


def main():
    with open(INPUT_CSV, encoding="utf-8") as f:
        candidates = list(csv.DictReader(f))
    print(f"{len(candidates)} candidates in {INPUT_CSV}")

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.setdefault("composers", {})

    todo = [c for c in candidates if f"new:{c['wikidata_id']}" not in entries]
    print(f"{len(todo)} not yet cached, {len(candidates) - len(todo)} already cached")

    fetched = 0
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        ids = "|".join(c["wikidata_id"] for c in batch)
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": ids,
             "props": "labels|descriptions|claims|sitelinks"},
        )
        wd_entities = result.get("entities", {})
        for c in batch:
            qid = c["wikidata_id"]
            entity = wd_entities.get(qid)
            if entity is None:
                continue
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            descriptions = {lang: v["value"] for lang, v in entity.get("descriptions", {}).items()}
            entries[f"new:{qid}"] = {
                "name": c["name"], "qid": qid, "labels": labels, "descriptions": descriptions,
                "relationships": extract_relationships(entity), "attributes": extract_attributes(entity),
                "dates": extract_dates(entity), "sitelinks": extract_sitelinks(entity),
                "source": INPUT_CSV,
            }
            fetched += 1
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {fetched} newly fetched, {len(entries)} total composer entries in cache.")


if __name__ == "__main__":
    main()

"""One-time backfill: add a Russian ("ru") label for a hardcoded list of 64
composers who have a Soviet/Russian-Empire signal in their cached
citizenship_text/place_of_birth_text/place_of_death_text (e.g. Aram
Khachaturian: nationality tagged only "Armenian", but died in Moscow under
Soviet citizenship) yet no Russian label was ever fetched, since the
nationality-driven language selection had nothing to key off of for them.

This list was found by scanning wikidata_relationships.json for entries
matching /Soviet|USSR|Russian (Empire|SFSR)|Russia\\b/ or a Russian/Soviet
city name (Moscow, Leningrad, St. Petersburg, Petrograd) in those three
text fields, with no "ru" key in labels yet -- not a general "everyone
gets Russian" pass, just these specific, already-identified composers.

Do not run this at the same time as `cli.py fetch ...`/`cli.py backfill
...` or another backfill_*.py script -- see README.md's "Pipeline rules"
for the concurrent-cache-write hazard.

Usage:
    python3 backfill_russian_labels.py
"""
import json
import time

from fetch_wikidata_relationships import OUTPUT_FILE, api_get

COMPOSER_IDS = [
    2463, 2534, 2535, 2536, 2537, 2539, 2541, 2543, 2544, 2546, 2549, 2550,
    2552, 2553, 2554, 2556, 2558, 2560, 2561, 2562, 2563, 2564, 2566, 2568,
    2573, 2574, 2575, 2829, 2943, 2962, 3016, 3162, 3383, 3477, 3664, 3748,
    4001, 4153, 4213, 4243, 4392, 4440, 4562, 4620, 4812, 4891, 4893, 4895,
    4918, 4990, 4996, 5285, 5348, 5381, 5433, 5594, 5727, 5839, 5970, 5974,
    5977, 6065, 6176, 6319,
]


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["composers"]

    todo = [
        (cid, entries[str(cid)]) for cid in COMPOSER_IDS
        if str(cid) in entries and entries[str(cid)].get("qid")
        and "ru" not in entries[str(cid)].get("labels", {})
    ]
    print(f"{len(todo)}/{len(COMPOSER_IDS)} still need a Russian label (rest already have one or are missing)")

    qids = [e["qid"] for _, e in todo]
    entry_by_qid = {e["qid"]: e for _, e in todo}

    added = 0
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "ru"},
        )
        for qid, entity in result.get("entities", {}).items():
            ru_label = entity.get("labels", {}).get("ru")
            if ru_label:
                entry_by_qid[qid]["labels"]["ru"] = ru_label["value"]
                added += 1
        time.sleep(0.3)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"done -- added a Russian label for {added}/{len(todo)} composers")


if __name__ == "__main__":
    main()

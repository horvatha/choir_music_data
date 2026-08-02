"""Fetch each musical key's name in *every* language Wikidata has a label
for. Keys are the QIDs cached under work_attributes' "tonality" field
(Wikidata P826) by fetch_work_details.py -- a different set of QIDs from
the works themselves (e.g. Q193526 "D minor"), so they need their own
fetch, same reasoning as fetch_genre_names.py for genres.

Caches into wikidata_relationships.json under "key_labels":
{qid: {language: name, ...}}, all languages included.

Usage:
    python3 fetch_key_names.py            # only keys missing a cached entry
    python3 fetch_key_names.py --recheck   # re-fetch every key too
"""
import json
import sys

from fetch_wikidata_relationships import OUTPUT_FILE, api_get


def main():
    recheck = "--recheck" in sys.argv

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})
    key_labels = data.setdefault("key_labels", {})

    qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("tonality", [])})
    todo = sorted(q for q in qids if recheck or q not in key_labels)
    print(f"{len(todo)} distinct keys to fetch names for" + (" (rechecking all)" if recheck else ""))

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels"},
        )
        for qid, entity in result.get("entities", {}).items():
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            key_labels[qid] = labels
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {len(key_labels)} distinct key QIDs cached.")


if __name__ == "__main__":
    main()

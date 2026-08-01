"""Fetch each genre's name in *every* language Wikidata has a label for.
Genres are the QIDs cached under work_attributes' "form_of_creative_work"
field (Wikidata P7937) by fetch_work_details.py -- these are a different
set of QIDs from the works themselves (e.g. Q214972 "cantata"), so they
need their own fetch; genres don't have DB rows yet at this point (that's
load_genres.py's job), so the QID list comes from the JSON cache, not a DB
query, unlike fetch_instrument_names.py.

Caches into wikidata_relationships.json under "genre_labels":
{qid: {language: name, ...}}, all languages included -- same reasoning as
work_labels (see fetch_work_details.py): caching every language means
growing TARGET_LANGUAGES later only needs a rerun of load_genres.py, not
another fetch.

Usage:
    python3 fetch_genre_names.py            # only genres missing a cached entry
    python3 fetch_genre_names.py --recheck   # re-fetch every genre too
"""
import json
import sys

from fetch_wikidata_relationships import OUTPUT_FILE, api_get


def main():
    recheck = "--recheck" in sys.argv

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_attributes = data.get("work_attributes", {})
    genre_labels = data.setdefault("genre_labels", {})

    qids = sorted({q for attrs in work_attributes.values() for q in attrs.get("form_of_creative_work", [])})
    todo = sorted(q for q in qids if recheck or q not in genre_labels)
    print(f"{len(todo)} distinct genres to fetch names for" + (" (rechecking all)" if recheck else ""))

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels"},
        )
        for qid, entity in result.get("entities", {}).items():
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            genre_labels[qid] = labels
        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {len(genre_labels)} distinct genre QIDs cached.")


if __name__ == "__main__":
    main()

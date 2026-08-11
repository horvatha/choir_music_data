"""Fetch each work's name in *every* language Wikidata has a label for,
plus a set of other musically-relevant claims, for works that already have
a wikidata_id (see load_works.py). One wbgetentities call per batch
already returns the full entity -- pulling labels and claims together
costs no extra API requests over labels alone.

Caches into wikidata_relationships.json under two keys:

- "work_labels": {qid: {language: name, ...}}, all languages included (not
  just TARGET_LANGUAGES -- see CLAUDE.md's "Target languages for
  translated names"). `cli.py load names --entity work` reads this and
  writes work_names, filtering down to TARGET_LANGUAGES at load time.
  Caching every language means growing that list later only needs a
  rerun of the loader, not another fetch.

- "work_attributes": {qid: {field: [...values], ...}}, one entry per
  CLAIM_PROPERTIES field that the work actually has a claim for (fields
  with no claims are omitted, not stored empty). Values are either raw
  QIDs (for wikibase-item claims -- entity resolution deferred, same as
  qid_labels elsewhere in this pipeline), Wikidata's raw time dict (for
  date claims -- {"time": "+1730-00-00T00:00:00Z", "precision": 9, ...},
  precision 9 = year, 10 = month, 11 = day), or plain strings (catalog
  code, CPDL ID). Nothing here is loaded into Postgres yet -- there is no
  load_work_details.py -- this only builds the cache so a future loader
  doesn't need another round of API calls.

Supersedes fetch_hu_names.py's "hu_names" for works -- that script only
ever fetched the "hu" label. hu_names is left alone (still used for
countries/places) but no longer needed for works once this has been run.

Usage:
    python3 fetch_work_details.py            # only works missing a cached entry
    python3 fetch_work_details.py --recheck   # re-fetch every work too
"""
import json
import sys

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, api_get

FETCH_WORKS_SQL = "SELECT id, wikidata_id FROM works WHERE wikidata_id IS NOT NULL"

# property -> (field name, datatype). datatype drives how the mainsnak's
# datavalue is pulled out (see extract_claim_values).
CLAIM_PROPERTIES = {
    "P571": ("inception", "time"),
    "P1191": ("first_performance", "time"),
    "P577": ("publication_date", "time"),
    "P7937": ("form_of_creative_work", "item"),
    "P528": ("catalog_code", "string"),
    "P826": ("tonality", "item"),
    "P870": ("instrumentation", "item"),
    "P495": ("country_of_origin", "item"),
    "P407": ("language_of_work", "item"),
    "P676": ("lyricist", "item"),
    "P87": ("librettist", "item"),
    "P50": ("author", "item"),
    "P2000": ("cpdl_id", "string"),
}


def extract_claim_values(claims, datatype):
    values = []
    for statement in claims:
        datavalue = statement.get("mainsnak", {}).get("datavalue")
        if not datavalue:
            continue
        values.append(datavalue["value"]["id"] if datatype == "item" else datavalue["value"])
    return values


def main():
    recheck = "--recheck" in sys.argv

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    work_labels = data.setdefault("work_labels", {})
    work_attributes = data.setdefault("work_attributes", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_WORKS_SQL)
            qids = sorted({wikidata_id for _id, wikidata_id in cur.fetchall()})
    finally:
        conn.close()

    todo = sorted(q for q in qids if recheck or q not in work_labels)
    print(f"{len(todo)} distinct works to fetch names/attributes for" + (" (rechecking all)" if recheck else ""))

    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels|claims"},
        )
        for qid, entity in result.get("entities", {}).items():
            labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
            work_labels[qid] = labels

            claims = entity.get("claims", {})
            attributes = {}
            for prop, (field, datatype) in CLAIM_PROPERTIES.items():
                if prop not in claims:
                    continue
                values = extract_claim_values(claims[prop], datatype)
                if values:
                    attributes[field] = values
            if attributes:
                work_attributes[qid] = attributes

        print(f"  {min(i + 50, len(todo))}/{len(todo)}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"done -- {len(work_labels)} distinct work QIDs cached "
          f"({len(work_attributes)} with at least one extra attribute).")


if __name__ == "__main__":
    main()

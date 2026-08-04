"""Fetch *every* language Wikidata has a label for, for a small
hand-picked list of composers whose name genuinely differs (not just
transliterates) across languages -- royalty/nobility with regnal names
and translated epithets (e.g. Q33550 "Frederick the Great" ->
"Friedrich II. von Preußen" in de, "Frédéric II de Prusse" in fr,
"Fryderyk II Wielki" in pl, ...) and composers known by a translated
descriptive byname ("the Elder"/"the Younger"/"the Stammerer"/"of
Arezzo"/...).

Unlike the rest of the composer population, fetch_wikidata_relationships.py
only ever asked for a composer's own BASE_LABEL_LANGUAGES (en/hu/ru) plus
one nationality-derived language -- fine for composers whose name is
basically the same Latin-script string everywhere, but these composers'
names are substantively different per language, so the narrower fetch
leaves most of that translation on the table.

Overwrites each composer's "labels" entry in wikidata_relationships.json
with the full fetched set (superset of whatever was cached before -- any
language previously cached is still included if Wikidata still has it).
load_composer_alt_names.py already loads *every* language present in
"labels" (not just a target subset), so it just needs rerunning after
this -- no changes needed there.

Usage:
    python3 fetch_curated_composer_names.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE, api_get

# Composer IDs whose translated name is a genuine per-language translation
# (regnal name + translated epithet/title, or a translated descriptive
# byname), not just a transliteration -- found by hand, see chat history
# for how each was surfaced (English-epithet-pattern search + noble-title
# search over composers.name).
CURATED_COMPOSER_IDS = {
    1: "Notker the Stammerer (Notker Balbulus)",
    7: "Odo of Arezzo (Abbot Oddo)",
    12: "Wulfstan the Cantor (Wulfstan of Winchester)",
    14: "Arnold of Saint Emmeram",
    15: "Otloh of Sankt Emmeram",
    20: "William IX, Duke of Aquitaine",
    85: "Franco of Cologne",
    102: "Mönch von Salzburg (Monk of Salzburg)",
    154: "Roy Henry (probably Henry V of England)",
    182: "William Cornysh the younger",
    192: "Henry VIII of England",
    254: "Alfonso Ferrabosco the younger",
    284: "John Hilton the younger",
    552: "Alfonso Ferrabosco the elder",
    662: "Mateo Flecha the Elder",
    827: "John IV of Portugal",
    828: "Mateo Flecha the Younger",
    1068: "Lady Mary Dering",
    1278: "Monsieur de Sainte-Colombe (the younger)",
    1591: "Johann Bernhard Bach (the younger)",
    1649: "Princess Wilhelmine of Prussia",
    1668: "Frederick the Great",
    1682: "Princess Philippine Charlotte of Prussia",
    1690: "Anna Amalia, Abbess of Quedlinburg",  # merged with 1748 "...Princess of Prussia", same Q237754
    1795: "Thomas Linley the elder",
    1821: "Anna Amalia, Duchess of Saxe-Weimar-Eisenach",
    1829: "Samuel Webbe the elder",
    1930: "Thomas Linley the younger",
    2009: "Samuel Webbe the younger",
    2119: "Oscar I of Sweden",
    2153: "Princess Amalie of Saxony",
    2256: "Prince Gustaf, Duke of Uppland",
}


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.setdefault("composers", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, wikidata_id FROM composers WHERE id = ANY(%s)",
                (list(CURATED_COMPOSER_IDS),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    missing = CURATED_COMPOSER_IDS.keys() - {r[0] for r in rows}
    if missing:
        print(f"warning: no DB row (renamed/merged since?) for ids: {sorted(missing)}")

    qids = [(composer_id, wikidata_id) for composer_id, wikidata_id in rows if wikidata_id]
    print(f"{len(qids)} of {len(CURATED_COMPOSER_IDS)} curated composers have a wikidata_id")

    for composer_id, qid in qids:
        result = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": qid, "props": "labels"},
        )
        entity = result.get("entities", {}).get(qid, {})
        labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
        entry = entries.setdefault(str(composer_id), {"applied_to_db": True})
        entry["labels"] = labels
        print(f"  {composer_id} ({qid}): {len(labels)} labels")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("done.")


if __name__ == "__main__":
    main()

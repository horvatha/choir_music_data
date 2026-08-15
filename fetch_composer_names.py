"""Fetch *every* language Wikidata has a label for, for --ids and/or the
--curated hand-picked list -- for composers whose translated name is a
genuine per-language translation, not just a transliteration (regnal
names + translated epithets/titles, e.g. Q33550 "Frederick the Great" ->
"Friedrich II. von Preußen" in de, "Frédéric II de Prusse" in fr,
"Fryderyk II Wielki" in pl, ...; or a translated descriptive byname like
"the Elder"/"the Younger"/"the Stammerer"/"of Arezzo"). The normal
`fetch composers` run only ever asks for BASE_LABEL_LANGUAGES (en/hu/ru)
plus one nationality-derived language -- fine for composers whose name is
basically the same Latin-script string everywhere, but leaves most of the
translation on the table for these.

--ids takes an arbitrary composer_id list (e.g. for a one-off "show me all
the name variations for the composers on this page" request). --curated
adds CURATED_COMPOSER_IDS, a small hand-picked list found by searching for
the English-epithet/noble-title pattern over composers.name -- see each
entry's own comment for how it was found. Both can be combined; ids from
either source are deduplicated.

Overwrites each composer's "labels" entry in wikidata_relationships.json
with the full fetched set (superset of whatever was cached before -- any
language previously cached is still included if Wikidata still has it).
load_composer_alt_names.py already loads *every* language present in
"labels" (not just a target subset) and never overwrites an existing alt
name, so it just needs rerunning after this -- no changes needed there.

Usage:
    python3 fetch_composer_names.py --ids 123 --ids 456
    python3 fetch_composer_names.py --curated
    python3 fetch_composer_names.py --ids 123 --curated
"""

import click
import psycopg2

from adapters.json_cache import load_cache, save_cache
from adapters.wikidata_api import api_get
from fetch_wikidata_relationships import OUTPUT_FILE

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


def fetch(composer_ids):
    data = load_cache(OUTPUT_FILE)
    entries = data.setdefault("composers", {})

    conn = psycopg2.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, wikidata_id FROM composers WHERE id = ANY(%s)", (composer_ids,))
            rows = cur.fetchall()
    finally:
        conn.close()

    missing = set(composer_ids) - {r[0] for r in rows}
    if missing:
        print(f"warning: no DB row for ids: {sorted(missing)}")

    qids = [(composer_id, wikidata_id) for composer_id, wikidata_id in rows if wikidata_id]
    print(f"{len(qids)} of {len(composer_ids)} composers have a wikidata_id")

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

    save_cache(OUTPUT_FILE, data)
    print("done.")


@click.command("composer-names")
@click.option("--ids", multiple=True, type=int, help="Composer ids to fetch full-language labels for (repeatable).")
@click.option("--curated", is_flag=True, help="Also fetch CURATED_COMPOSER_IDS (the hand-picked royalty/epithet list).")
def composer_names_command(ids, curated):
    """Fetch every Wikidata language label for --ids and/or --curated composers."""
    composer_ids = list(dict.fromkeys(list(ids) + (list(CURATED_COMPOSER_IDS) if curated else [])))
    if not composer_ids:
        raise click.UsageError("Give --ids and/or --curated.")
    fetch(composer_ids)


if __name__ == "__main__":
    composer_names_command()

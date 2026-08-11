"""Resolve a display name (into the shared qid_labels cache) for every
QID referenced in any composer's relationships/attributes but not yet
resolved -- same sweep fetch_wikidata_relationships.py's main() already
does at the end of a normal run, extracted as its own script since
composers loaded via fetch_missing_composers_from_relations.py/
fetch_candidate_people.py never go through that main() loop, so their
notable_work/genre/instrument/etc. QIDs need this pass run separately
before load_works.py (etc.) can resolve them to a name instead of leaving
the row skipped ("unresolved work names skipped").

Also retries any QID that's *in* qid_labels but mapped to itself --
get_labels() only ever asks for BASE_LABEL_LANGUAGES (en/hu/ru) + "mul",
so a QID whose Wikidata item has labels in neither (e.g. a Swedish parish
only labelled in "sv", or a person only labelled in "uk"/"pl"/"be") comes
back unresolved and gets cached as itself -- which then reads as "already
resolved" on every later run and is never retried. Found via composer_
relations/places/place_periods rows that ended up storing a literal
"Q123..." as father/mother/place name; confirmed several of these DO have
a usable label once *any* language is allowed, not just the narrow three
(e.g. Q100109475 has pl/nl "Maciej Każyński", nothing in en/hu/ru).

Usage:
    python3 resolve_qid_labels.py
"""
import json

from fetch_wikidata_relationships import OUTPUT_FILE, api_get, get_labels


def _resolve_any_language(qids: list[str]) -> dict:
    """Like get_labels(), but omits the `languages` param entirely so
    Wikidata returns every label the item has, preferring "en" and
    otherwise taking whatever comes back first -- last resort for a QID
    BASE_LABEL_LANGUAGES already failed to resolve."""
    labels = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch), "props": "labels"},
        )
        for qid, entity in data.get("entities", {}).items():
            entity_labels = entity.get("labels", {})
            preferred = entity_labels.get("en") or next(iter(entity_labels.values()), None)
            if preferred:
                labels[qid] = preferred["value"]
    return labels


def main():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    entries = data["composers"]
    label_cache = data.setdefault("qid_labels", {})

    # Same string-vs-list guard as fetch_wikidata_relationships.py's own
    # sweep: some older entries mix in plain-string summary fields
    # alongside the QID lists.
    all_qids = {
        q for e in entries.values()
        for group in (e.get("relationships", {}), e.get("attributes", {}))
        for qs in group.values() if isinstance(qs, list)
        for q in qs
    }
    unresolved = sorted(q for q in all_qids if q not in label_cache)
    print(f"{len(unresolved)} unresolved QIDs out of {len(all_qids)} referenced")
    if unresolved:
        label_cache.update(get_labels(unresolved))

    self_referential = sorted(q for q in all_qids if label_cache.get(q) == q)
    print(f"{len(self_referential)} QIDs resolved to themselves (no en/hu/ru/mul label) -- retrying broadly")
    if self_referential:
        label_cache.update(_resolve_any_language(self_referential))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("done.")


if __name__ == "__main__":
    main()

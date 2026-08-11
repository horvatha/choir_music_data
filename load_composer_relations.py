"""Load composer_relations from the RELATIONSHIP_PROPS already fetched into
wikidata_relationships.json by fetch_wikidata_relationships.py (father,
mother, student_of, notable_student, doctoral_advisor, influenced_by).

related_wikidata_id is always populated straight from Wikidata;
related_composer_id is only set when the other person's QID matches an
existing composers.wikidata_id, so a relation can point to someone who
isn't (yet) in this DB at all -- most don't, going by the one-time check
that found only ~200 of ~900 distinct related QIDs match an existing
composer. When it does match, related_name is taken from that composer's
own (verified) composers.name rather than the qid_labels cache -- Wikidata's
"en" label is preferred over "hu" whenever one exists (see get_labels in
fetch_wikidata_relationships.py), which for Hungarian names sometimes drops
long accents entirely (e.g. Wikidata's own English label for Q709178 is
"Jenö Hubay", missing the "o"-with-double-acute in "Jenő"); composers.name
doesn't have that problem since it's cross-checked against other sources.

Skips a relation entirely when the related person isn't an existing
composer AND Wikidata's own label for them is its "unknown given name"
placeholder (a literal "???" standing in for an unrecorded first name,
e.g. "??? Hässler" for a composer's father known only by surname) -- that
conveys zero information (everyone has a father/mother; a stub entity with
no name, no description, and no other claims doesn't tell us anything a
plain composers row for them wouldn't already imply), so it's not worth a
row. Confirmed via direct Wikidata lookup that entities like this really
do have no en/other-language label and no description at all, not just a
gap in what's been fetched.

EXCLUDED_RELATIONS drops specific (composer wikidata_id, relation_type,
related wikidata_id) triples that are real Wikidata claims but belong to
a non-musical side of a composer's life -- same reasoning and review
process as load_works.py's EXCLUDED_QIDS for non-musical "notable work"
claims. Keyed on relation_type too, not just the two people, since the
same related person can appear under more than one relation_type for the
same composer with only one of them being music-relevant (e.g. William
Herschel's son is both his "child" -- kept, a plain genealogical fact --
and his "notable_student" -- excluded, since that claim is about
astronomy/mathematics mentorship, not music).
"""
import json
import re

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

FETCH_COMPOSER_ID_BY_WIKIDATA_SQL = "SELECT id FROM composers WHERE wikidata_id = %s"
UNKNOWN_NAME_RE = re.compile(r"^\?+\s")

EXCLUDED_RELATIONS = {
    # William Herschel: dual composer/astronomer career: P184 doctoral
    # advisor Nevil Maskelyne (Astronomer Royal who sponsored/verified his
    # telescope observations) and P802 notable student John Frederick
    # William Herschel (his son, became an astronomer/mathematician) are
    # both genuine Wikidata claims but purely about his astronomy career.
    ("Q14277", "doctoral_advisor", "Q450757"),
    ("Q14277", "notable_student", "Q14278"),
}

UPSERT_RELATION_SQL = """
    INSERT INTO composer_relations
        (composer_id, relation_type, related_name, related_wikidata_id, related_composer_id)
    VALUES (%(composer_id)s, %(relation_type)s, %(related_name)s, %(related_wikidata_id)s, %(related_composer_id)s)
    ON CONFLICT (composer_id, relation_type, related_wikidata_id) DO UPDATE
        SET related_name = EXCLUDED.related_name, related_composer_id = EXCLUDED.related_composer_id
"""


def load():
    """Fully rebuilds composer_relations from wikidata_relationships.json.
    Not incremental -- truncates first, so reruns after a fresh fetch don't
    leave stale relations for composers whose recorded relationships
    changed upstream."""
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    qid_labels = data.get("qid_labels", {})

    conn = psycopg2.connect()
    processed = 0
    stale = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_relations RESTART IDENTITY")

                # QID -> (composer_id, name), so each related person is looked
                # up once rather than once per relation.
                cur.execute("SELECT wikidata_id, id, name FROM composers WHERE wikidata_id IS NOT NULL")
                composer_by_qid = {qid: (cid, name) for qid, cid, name in cur.fetchall()}
                cur.execute("SELECT id FROM composers")
                real_composer_ids = {r[0] for r in cur.fetchall()}

                for composer_id, entry in data["composers"].items():
                    if not entry.get("applied_to_db"):
                        continue
                    if not composer_id.isdigit() or int(composer_id) not in real_composer_ids:
                        # Stale cache id -- see README.md's "Pipeline
                        # rules" (stale cache ids after a merge).
                        stale += 1
                        continue
                    relationships = entry.get("relationships", {})
                    if not relationships:
                        continue
                    processed += 1
                    own_qid = entry.get("qid")
                    for relation_type, qids in relationships.items():
                        for qid in qids:
                            if (own_qid, relation_type, qid) in EXCLUDED_RELATIONS:
                                continue
                            related_composer_id, related_name = composer_by_qid.get(qid, (None, None))
                            related_name = related_name or qid_labels.get(qid, qid)
                            if related_composer_id is None and UNKNOWN_NAME_RE.match(related_name):
                                continue
                            cur.execute(UPSERT_RELATION_SQL, {
                                "composer_id": int(composer_id),
                                "relation_type": relation_type,
                                "related_name": related_name,
                                "related_wikidata_id": qid,
                                "related_composer_id": related_composer_id,
                            })
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one relationship"
          + (f", skipped {stale} stale cache entries" if stale else "") + ".")


if __name__ == "__main__":
    load()

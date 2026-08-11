"""Load works from the "notable_work" (P800) attribute already fetched
into wikidata_relationships.json by `cli.py fetch composers`
(--era/--nationality/--ids).

Unlike instruments this isn't a junction table -- a work has exactly one
composer, so works.composer_id is a plain FK, not a many-to-many pair.
wikidata_notable_work is set TRUE for every row here, since P800 is
specifically Wikidata's own "notable work" claim; a future, broader source
(e.g. a full works catalogue) adding rows for lesser-known works would
leave it FALSE, so the two can be told apart later.

Fully rebuilds the table each run (truncate first) -- same reasoning as
load_instruments.py: reruns after a fresh fetch shouldn't leave stale rows
for a composer whose notable-work list changed upstream.

Usage:
    python3 load_works.py
"""
import json

import psycopg2

from fetch_wikidata_relationships import OUTPUT_FILE

# QIDs that turned up as P800 "notable work" values but are the composer's
# own non-musical writing (prose, novels, philosophical/theological
# treatises), not a musical work -- P800 doesn't distinguish "musical work"
# from "written work" for a person who did both. Found by reviewing
# fetch_work_details.py's "form_of_creative_work" cache for genres like
# "prose"/"novel"/"novella"/"narration" and checking each work by hand
# (same review process as load_tags.py's EXCLUDED_QIDS). Dropped entirely
# rather than loaded as a "work", same as EXCLUDED_QIDS there.
EXCLUDED_QIDS = {
    "Q692557",   # Anthony Burgess, "A Clockwork Orange" -- novel
    "Q358642",   # E.T.A. Hoffmann, "Mademoiselle de Scuderi" -- novella
    "Q837936",   # E.T.A. Hoffmann, "Master Flea" -- fairy tale/Erzählung
    "Q600849",   # E.T.A. Hoffmann, "The Devil's Elixirs" -- novel
    "Q744557",   # E.T.A. Hoffmann, "The Nutcracker and the Mouse King" -- novelette
    "Q3049558",  # Hildegard of Bingen, "Liber divinorum operum" -- prose
    "Q3045605",  # Hildegard of Bingen, "Scivias" -- narration
    "Q913599",   # Jean-Jacques Rousseau, "Emile, or On Education" -- narration
    "Q42188021", # Odo of Cluny, "Collationes" -- prose
    "Q42189653", # Peter Abelard, "Ethica" -- prose
    "Q42189772", # Peter Abelard, "Expositio in Epistolam ad Romanos" -- prose
    "Q2960332",  # Peter Abelard, "Historia Calamitatum" -- prose
    "Q54030749", # William Herschel, "Account of a Comet" -- astronomy paper
    "Q21002732", # William Herschel, discovery of Uranus -- astronomy
    "Q600076",   # William Herschel, Herschel wedge -- astronomy/optics device
    "Q11388",    # William Herschel, infrared radiation -- physics discovery
}

UPSERT_WORK_SQL = """
    INSERT INTO works (composer_id, name, wikidata_id, wikidata_notable_work)
    VALUES (%s, %s, %s, TRUE)
    ON CONFLICT (composer_id, wikidata_id) DO UPDATE
        SET name = EXCLUDED.name, wikidata_notable_work = TRUE
"""


def load():
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    qid_labels = data.get("qid_labels", {})

    conn = psycopg2.connect()
    processed = 0
    skipped = 0
    stale = 0
    try:
        with conn:
            with conn.cursor() as cur:
                # CASCADE: work_names/work_genres/work_musical_keys/
                # work_instruments all reference works.id and didn't exist
                # when this plain TRUNCATE was first written -- rerunning
                # any of `cli.py load names --entity work`/load_genres.py/
                # load_musical_keys.py/load_work_instruments.py afterward
                # is required, same as the composed_*/premiered_*/
                # published_*/catalog_code/cpdl_id columns on works itself
                # (load_work_dates.py/load_work_catalog_info.py) needing a
                # rerun since they're columns on the row just wiped.
                cur.execute("TRUNCATE works RESTART IDENTITY CASCADE")
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
                    work_qids = entry.get("attributes", {}).get("notable_work", [])
                    if not work_qids:
                        continue
                    processed += 1
                    for qid in work_qids:
                        if qid in EXCLUDED_QIDS:
                            continue
                        name = qid_labels.get(qid, qid)
                        if name == qid:
                            # Not resolved yet (e.g. the fetch that
                            # introduced this composer hasn't reached its
                            # end-of-run label-resolution pass) -- skip
                            # rather than load the raw QID as a "name";
                            # rerun once qid_labels has caught up.
                            skipped += 1
                            continue
                        cur.execute(UPSERT_WORK_SQL, (int(composer_id), name, qid))
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one notable work "
          f"({skipped} unresolved work names skipped"
          + (f", {stale} stale cache entries skipped" if stale else "") + ").")


if __name__ == "__main__":
    load()

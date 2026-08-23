"""Load tags/composer_tags from the "movement" (P135) attribute already
fetched into wikidata_relationships.json by fetch_wikidata_relationships.py.
See schema.sql's comment on the tags table for why this repo calls
Wikidata's "movement" property "tags" instead.

Unlike load_instruments.py, wikidata_id (not name) is the upsert key here --
two distinct Wikidata items can share the identical English label (e.g.
Q2426218 and Q878985 both label as plain "modernism"), so name alone would
silently merge unrelated tags together.

EXCLUDED_QIDS and QID_REDIRECTS are hand-maintained curation, found by
reviewing the full tag list by hand (same spirit as classify_hu_wiki_
composers.py's category-keyword review, just for tags instead of pop-vs-
concert-music). See the entries below for why each one was added.
"""

import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

# Hand-maintained renames for tags whose plain Wikidata label collides with
# a different QID's label -- same pattern as this repo's other hand
# override lists (ERA_OVERRIDES, MANUAL_PLACE_CLUSTERS). Add an entry here
# once a collision like this is found; see schema.sql's tags comment.
NAME_OVERRIDES = {
    "Q2426218": "musical modernism",  # vs Q878985 "modernism" (the general movement)
}

# QIDs that turned up as P135 "movement" values but aren't real, usable
# movement concepts -- dropped entirely rather than loaded as a tag.
EXCLUDED_QIDS = {
    "Q28820001",  # "musical scene" -- Wikidata's own description is a generic
                  # placeholder ("a musical culture within a well-defined
                  # region and/or time-period"), not an actual named movement.
    "Q3328677",   # "Partitions de musique festive de danses de Paris au
                  # XIXème siècle" -- has no Wikidata description and no P31
                  # (instance of) claim at all; looks like a mis-scraped
                  # sheet-music collection/publication title, not a movement.
    "Q213457",    # "Beat Generation" -- a literary movement, not a musical
                  # one; picked up via Paul Bowles's P135 claims (he's a
                  # genuine composer -- studied under Copland, wrote
                  # theatrical/concert works -- but his Beat Generation
                  # association is literary, from his later writing career).
                  # Not a case of one mistagged composer: this movement
                  # concept itself isn't a musical-composer classification,
                  # so it's excluded outright rather than per-composer.

    # Era-duplicates: bare era names and "X music"/"X period" variants that
    # add nothing composer_eras doesn't already say (see
    # eras/composer_eras in schema.sql). Found via reports/tags_review.md's
    # full hand-review of every tag, 2026-08-23.
    "Q8361",      # Baroque music
    "Q37853",     # Baroque
    "Q4692",      # Renaissance
    "Q201405",    # Renaissance music
    "Q163775",    # medieval music
    "Q207591",    # Romantic music
    "Q37068",     # Romanticism
    "Q17723",     # Classical period
    "Q170292",    # Classicism
    "Q9730",      # classical music -- also just too generic: nearly every
                  # composer in this database is a classical-music composer
                  # by definition, and it was only inconsistently applied.
    "Q1338153",   # 20th-century classical music
    "Q4631020",   # 21st-century classical music
    "Q612024",    # contemporary classical music
    "Q65937946",  # modern classical music
    "Q2534081",   # pre-classical music
    "Q8011523",   # contemporary music

    # Era + nationality combinations: derivable from era + the composer's
    # own nationality (composer_nationalities), both already tracked
    # structurally -- not a distinct named school the way e.g. "Franco-
    # Flemish School" or "Roman School" are (those stay as real tags).
    "Q2455000",   # German Renaissance
    "Q3328590",   # French baroque music
    "Q2477112",   # German Romanticism
    "Q1542287",   # Ukrainian Baroque
    "Q5249786",   # New Spanish Baroque

    # Clearly non-musical (philosophy, religion, politics, or another art
    # form entirely, with no real musical anchor).
    "Q169390",    # abolitionism
    "Q177725",    # abstract expressionism
    "Q34636",     # Art Nouveau
    "Q59104",     # continental philosophy
    "Q10710179",  # Enlightenment philosophy
    "Q1246516",   # feminist art
    "Q290209",    # Flemish Movement
    "Q151843",    # Frankfurt School
    "Q41726",     # freemasonry
    "Q3401112",   # medieval poetry
    "Q202253",    # nominalism
    "Q23540",     # Protestantism
    "Q12562",     # Protestant Reformation
    "Q877848",    # Republicanism
    "Q5977111",   # Romantic literature
    "Q263985",    # romantic nationalism -- political/cultural-historical
                  # concept; "musical nationalism" (Q1196170) stays as the
                  # music-scoped version of the same idea.
    "Q41679",     # scholasticism
    "Q164800",    # Symbolism -- primarily literary/visual-art, no specific
                  # musical anchor the way e.g. "impressionism in music"
                  # (kept) explicitly has.

    # Too generic -- a more specific, music-scoped tag already covers the
    # same ground.
    "Q6235",      # nationalism (vs "musical nationalism", kept)
    "Q878985",    # modernism (vs "musical modernism", kept)
    "Q47783",     # Postmodernism (vs "postmodern music", kept)

    # Redundant with structured data already tracked elsewhere.
    "Q155858",    # music of Ukraine -- redundant with composer_nationalities.

    # Likely a P135 mistagging of the musical *form* "Romance" (a piece
    # type, like Nocturne/Ballade) as a "movement", not a genuine
    # stylistic movement.
    "Q599510",    # romance
}

# QID -> QID: silently redirect a mistagged movement value to the one it
# almost certainly should have been. Q14378 "Neoclassicism" is the general
# 18th-century Greek/Roman-revival art movement (architecture, painting) --
# unrelated to music, and confirmed via Wikidata's own P31 typing (Q14378
# has no "musical movement" instance-of, only "art movement"). The only
# composer who ever carried it (Alfred Reed, a 20th-century American band
# composer) almost certainly should carry Q535611 "neoclassicism" instead --
# explicitly typed by Wikidata as a "twentieth-century movement in music",
# and the two are easy to confuse since musical Neoclassicism took its very
# name from the earlier art-historical movement as a deliberate allusion.
QID_REDIRECTS = {
    "Q14378": "Q535611",
}

UPSERT_TAG_SQL = """
    INSERT INTO tags (name, wikidata_id) VALUES (%s, %s)
    ON CONFLICT (wikidata_id) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
"""

LINK_TAG_SQL = """
    INSERT INTO composer_tags (composer_id, tag_id)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def load():
    """Fully rebuilds tags/composer_tags from wikidata_relationships.json.
    Not incremental -- truncates first, so reruns after a fresh fetch don't
    leave stale links for composers whose recorded tags changed upstream."""
    data = load_cache(OUTPUT_FILE)
    qid_labels = data.get("qid_labels", {})

    conn = psycopg2.connect()
    processed = 0
    stale = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE composer_tags, tags RESTART IDENTITY CASCADE")
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
                    tag_qids = entry.get("attributes", {}).get("movement", [])
                    if not tag_qids:
                        continue
                    processed += 1
                    for qid in tag_qids:
                        qid = QID_REDIRECTS.get(qid, qid)
                        if qid in EXCLUDED_QIDS:
                            continue
                        name = NAME_OVERRIDES.get(qid, qid_labels.get(qid, qid))
                        cur.execute(UPSERT_TAG_SQL, (name, qid))
                        tag_id = cur.fetchone()[0]
                        cur.execute(LINK_TAG_SQL, (int(composer_id), tag_id))
    finally:
        conn.close()
    print(f"Processed {processed} composers with at least one tag"
          + (f", skipped {stale} stale cache entries" if stale else "") + ".")


if __name__ == "__main__":
    load()
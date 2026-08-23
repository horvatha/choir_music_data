"""Set places.place_type (Wikidata P31 label) and places.parent_place_id
(current administrative parent, Wikidata P131) for places that are
currently part of a larger place we track -- e.g. a Budapest district or
an NYC borough -- populate place_predecessors for places that used to be
their own separate administrative entity but no longer exist in that
form -- e.g. Tokyo City (dissolved 1943) or East/West Berlin (reunified
1990) -- and set places.located_in_place_id for a non-administrative
landmark (a street, a building) physically located inside a settlement
-- e.g. boulevard Saint-Michel -> Paris. See the place_type/
parent_place_id/located_in_place_id comment above CREATE TABLE places,
and place_predecessors' own table comment, in schema.sql for why these
are different relationships rather than one.

All dicts below are hand-confirmed judgment calls, the same way
MANUAL_PLACE_CLUSTERS in load_birth_death_places.py is: verified against
Wikidata's own P31/P131/P1366 claims one city at a time rather than
derived automatically, since blindly trusting P131 breaks down close to
Budapest's case (Buda's own P131 happens to also point at Budapest, even
though it's a historical predecessor, not a current district -- see
load_birth_death_places.py's docstring on why a full place_periods merge
was reverted for that group).

Assumes every QID here already has a places/place_periods row -- i.e.
some composer's birth/death place already resolved there via
load_birth_death_places.py, or (Óbuda's case, no composer references it
yet) it was seeded by hand. Prints a warning and skips anything not
already tracked, rather than creating it, to keep this script's job
narrowly "set relationships" rather than duplicating
load_birth_death_places.py's window-building logic.

Usage:
    python3 load_place_hierarchy.py
"""
import psycopg2

# child_qid -> (parent_qid, place_type)
DISTRICT_PARENTS = {
    # Budapest's districts (current, active administrative units).
    "Q974038": ("Q1781", "district of Budapest"),  # District XII
    "Q851057": ("Q1781", "district of Budapest"),  # District XX
    "Q851062": ("Q1781", "district of Budapest"),  # District XXIII
    "Q597182": ("Q1781", "district of Budapest"),  # District VIII
    "Q697679": ("Q1781", "district of Budapest"),  # District VI
    "Q284541": ("Q1781", "district of Budapest"),  # District VII
    # New York City's boroughs.
    "Q18419": ("Q60", "borough of New York City"),  # Brooklyn
    "Q18426": ("Q60", "borough of New York City"),  # The Bronx
    "Q11299": ("Q60", "borough of New York City"),  # Manhattan
    "Q18424": ("Q60", "borough of New York City"),  # Queens
    # Paris arrondissements -- both current and pre-1860 "former" ones
    # (Paris itself never stopped existing, only the internal numbering/
    # boundaries changed in 1860) share the same P131 -> Paris, so both
    # get the same current-parent treatment rather than splitting former
    # ones into place_predecessors.
    "Q169293": ("Q90", "municipal arrondissement of France"), "Q161741": ("Q90", "municipal arrondissement of France"),
    "Q194420": ("Q90", "municipal arrondissement of France"), "Q238723": ("Q90", "municipal arrondissement of France"),
    "Q204622": ("Q90", "municipal arrondissement of France"), "Q270230": ("Q90", "municipal arrondissement of France"),
    "Q200126": ("Q90", "municipal arrondissement of France"), "Q197297": ("Q90", "municipal arrondissement of France"),
    "Q163948": ("Q90", "municipal arrondissement of France"), "Q275118": ("Q90", "municipal arrondissement of France"),
    "Q171689": ("Q90", "municipal arrondissement of France"), "Q187153": ("Q90", "municipal arrondissement of France"),
    "Q245546": ("Q90", "municipal arrondissement of France"), "Q191066": ("Q90", "municipal arrondissement of France"),
    "Q175129": ("Q90", "municipal arrondissement of France"),
    "Q2845754": ("Q90", "former arrondissement of Paris"), "Q2845756": ("Q90", "former arrondissement of Paris"),
    "Q2845761": ("Q90", "former arrondissement of Paris"), "Q2845760": ("Q90", "former arrondissement of Paris"),
    "Q2845753": ("Q90", "former arrondissement of Paris"), "Q15149908": ("Q90", "former arrondissement of Paris"),
    "Q2845750": ("Q90", "former arrondissement of Paris"),
    # London boroughs + the City of London -> Greater London (Q23306,
    # "administrative area and ceremonial county"), not "London" (Q84)
    # directly -- that's what their own P131 claims actually point to.
    # "London" itself (Q84, "capital and largest city...") is *also* its
    # own P131 child of Greater London on Wikidata -- the informal/common
    # city concept nests inside the formal administrative area, same as
    # the boroughs -- so it needs the same treatment, found 2026-07-20
    # after a composer search turned up composers on London's own page
    # missing from Greater London's unified list.
    "Q84": ("Q23306", "capital city"),  # London
    "Q215030": ("Q23306", "London borough"),  # Lewisham
    "Q205690": ("Q23306", "London borough"),  # Hillingdon
    "Q202059": ("Q23306", "London borough"),  # Lambeth
    "Q205817": ("Q23306", "London borough"),  # Islington
    "Q23311": ("Q23306", "city (historic core of London)"),  # City of London
}

# successor_qid -> [(predecessor_qid, place_type, display_order), ...]
# -- places that were their own separate administrative entity and no
# longer exist in that form.
HISTORICAL_PREDECESSORS = {
    "Q1781": [  # Budapest, unified 1873
        ("Q25394915", "town", 0),  # Óbuda
        ("Q193478", "city", 1),  # Buda
        ("Q210205", "neighborhood (formerly independent city)", 2),  # Pest
    ],
    "Q7473516": [  # Tokyo (the 23-special-wards entity), both dissolved 1943
        ("Q1207735", "historic city (1889-1943)", 0),  # Tokyo City
        ("Q1189121", "former prefecture (1868-1943)", 1),  # Tokyo Prefecture
    ],
    "Q64": [  # Berlin, reunified 1990
        ("Q56037", "former Soviet sector (1945-1990)", 0),  # East Berlin
        ("Q56036", "former Western sectors (1945-1990)", 1),  # West Berlin
    ],
}

# Places that just need place_type set, no parent/predecessor relationship.
TYPE_ONLY = {
    "Q1781": "national capital",  # Budapest
    "Q60": "consolidated city-county",  # New York City
}

# landmark_qid -> (settlement_qid, place_type) -- a non-administrative
# landmark (a street, a building) physically located inside a settlement,
# written to located_in_place_id, NOT parent_place_id: unlike a district/
# borough/arrondissement, a street has no local government of its own, so
# it's not "administratively part of" the city the way DISTRICT_PARENTS'
# entries are (see schema.sql's CREATE TABLE places comment). Never feeds
# the Parts/"Kerületek" admin-hierarchy grouping, but does feed the same
# unified composer list a district's parent_place_id triggers -- a
# landmark-linked composer shows up on both the landmark's own page and
# its settlement's page.
LANDMARK_LOCATIONS = {
    "Q895078": ("Q90", "street"),  # boulevard Saint-Michel -> Paris
    "Q2873662": ("Q90", "street"),  # avenue Gourgaud -> Paris
    "Q2921974": ("Q90", "street"),  # boulevard de Courcelles -> Paris
    "Q2922078": ("Q90", "street"),  # boulevard du Montparnasse -> Paris
    "Q2921894": ("Q90", "street"),  # boulevard Pereire -> Paris
    "Q3447053": ("Q90", "street"),  # rue Ballu -> Paris
    "Q3447168": ("Q90", "street"),  # rue Blanche -> Paris
    "Q3447453": ("Q90", "street"),  # rue Christophe-Colomb -> Paris
    "Q3447626": ("Q90", "street"),  # rue Dauphine -> Paris
    "Q3450713": ("Q90", "street"),  # rue de Douai -> Paris
    "Q1640681": ("Q90", "street"),  # rue de la Chaussée-d'Antin -> Paris
    "Q3451594": ("Q90", "street"),  # rue de la Verrerie -> Paris
    "Q48748327": ("Q90", "street"),  # Rue d'Enfer -> Paris
    "Q3451060": ("Q90", "street"),  # rue de Steinkerque -> Paris
    "Q3452235": ("Q90", "street"),  # rue du Conservatoire -> Paris
    "Q2378296": ("Q90", "street"),  # rue Louise-Émilie-de-La-Tour-d'Auvergne -> Paris
    "Q3449529": ("Q90", "street"),  # rue Pierre-Larousse -> Paris
    "Q3449728": ("Q90", "street"),  # rue Richer -> Paris
    "Q1356926": ("Q90", "street"),  # rue Saint-Jacques -> Paris
    "Q3450116": ("Q90", "street"),  # rue Taitbout -> Paris
    "Q3450316": ("Q90", "street"),  # rue Victor-Massé -> Paris
    "Q137475146": ("Q42810", "street"),  # Rue Robert de la Villehervé -> Le Havre (NOT Paris -- verified via Wikidata P131)
    "Q24929623": ("Q48958", "street"),  # Boulevard d'Inkermann -> Neuilly-sur-Seine (NOT Paris -- verified via Wikidata P131)
    "Q3452020": ("Q3992", "street"),  # Rue des Récollets -> Liège (NOT Paris -- verified via Wikidata P131)
    "Q22249019": ("Q30974", "street"),  # Rue aux Ours, Rouen -> Rouen (own name already says Rouen; place_link's substring guard avoids "Rouen, Rouen")
}


def _place_id_for_qid(cur, qid):
    cur.execute("SELECT place_id FROM place_qids WHERE wikidata_id = %s", (qid,))
    row = cur.fetchone()
    return row[0] if row else None


def main():
    conn = psycopg2.connect()
    with conn:
        with conn.cursor() as cur:
            for child_qid, (parent_qid, place_type) in DISTRICT_PARENTS.items():
                child_id = _place_id_for_qid(cur, child_qid)
                parent_id = _place_id_for_qid(cur, parent_qid)
                if child_id is None or parent_id is None:
                    print(f"skip {child_qid} -> {parent_qid}: not yet tracked")
                    continue
                cur.execute(
                    "UPDATE places SET place_type=%s, parent_place_id=%s WHERE id=%s",
                    (place_type, parent_id, child_id),
                )

            for successor_qid, predecessors in HISTORICAL_PREDECESSORS.items():
                successor_id = _place_id_for_qid(cur, successor_qid)
                if successor_id is None:
                    print(f"skip predecessors of {successor_qid}: not yet tracked")
                    continue
                for pred_qid, place_type, order in predecessors:
                    pred_id = _place_id_for_qid(cur, pred_qid)
                    if pred_id is None:
                        print(f"skip predecessor {pred_qid} of {successor_qid}: not yet tracked")
                        continue
                    cur.execute("UPDATE places SET place_type=%s WHERE id=%s", (place_type, pred_id))
                    cur.execute(
                        "INSERT INTO place_predecessors (place_id, predecessor_place_id, display_order) "
                        "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        (successor_id, pred_id, order),
                    )

            for qid, place_type in TYPE_ONLY.items():
                place_id = _place_id_for_qid(cur, qid)
                if place_id is None:
                    print(f"skip {qid}: not yet tracked")
                    continue
                cur.execute("UPDATE places SET place_type=%s WHERE id=%s", (place_type, place_id))

            for landmark_qid, (settlement_qid, place_type) in LANDMARK_LOCATIONS.items():
                landmark_id = _place_id_for_qid(cur, landmark_qid)
                settlement_id = _place_id_for_qid(cur, settlement_qid)
                if landmark_id is None or settlement_id is None:
                    print(f"skip {landmark_qid} -> {settlement_qid}: not yet tracked")
                    continue
                cur.execute(
                    "UPDATE places SET place_type=%s, located_in_place_id=%s WHERE id=%s",
                    (place_type, settlement_id, landmark_id),
                )

    conn.close()
    print("done")


if __name__ == "__main__":
    main()

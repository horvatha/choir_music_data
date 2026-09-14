"""Set places.place_type (Wikidata P31 label) and places.parent_place_id
(current administrative parent, Wikidata P131) for places that are
currently part of a larger place we track -- e.g. a Budapest district or
an NYC borough -- populate place_predecessors for places that used to be
their own separate administrative entity but no longer exist in that
form -- e.g. Tokyo City (dissolved 1943) or East/West Berlin (reunified
1990) -- and set places.located_in_place_id for a non-administrative
landmark (a street, a building, a church parish, ...) physically located
inside a settlement -- e.g. boulevard Saint-Michel -> Paris, or Katarina
church parish -> Stockholm. See the place_type/parent_place_id/
located_in_place_id comment above CREATE TABLE places, and
place_predecessors' own table comment, in schema.sql for why these are
different relationships rather than one.

LANDMARK_LOCATIONS is the one dict here meant to grow with genuinely
different *categories* of landmark over time (started with Paris-area
streets, then 84 mostly-Swedish church parishes, both same fix shape) --
kept as a single dict/loop rather than one file per category precisely
so there's one place to look, not an ever-growing pile of near-identical
scripts.

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

# landmark_qid -> (settlement_qid, place_type, settlement_name) -- a
# non-administrative landmark (a street, a building, a church parish)
# physically located inside a settlement, written to located_in_place_id,
# NOT parent_place_id: unlike a district/borough/arrondissement, a street
# has no local government of its own, so it's not "administratively part
# of" the city the way DISTRICT_PARENTS' entries are (see schema.sql's
# CREATE TABLE places comment). Never feeds the Parts/"Kerületek" admin-
# hierarchy grouping, but does feed the same unified composer list a
# district's parent_place_id triggers -- a landmark-linked composer shows
# up on both the landmark's own page and its settlement's page.
#
# settlement_name is used only if the settlement itself isn't tracked yet
# (main() creates a new place row for it then) -- true for most of the
# smaller Swedish/Danish towns among the parishes below, which were only
# ever reachable through their parish, never referenced as a settlement
# in their own right by any composer's birth/death place directly.
#
# Streets (Paris-area, found 2026-08-23 via composers showing a bare
# country with no city -- P20 death-place claims sometimes point at a
# street-level Wikidata item rather than the city):
LANDMARK_LOCATIONS = {
    "Q895078": ("Q90", "street", "Paris"),  # boulevard Saint-Michel
    "Q2873662": ("Q90", "street", "Paris"),  # avenue Gourgaud
    "Q2921974": ("Q90", "street", "Paris"),  # boulevard de Courcelles
    "Q2922078": ("Q90", "street", "Paris"),  # boulevard du Montparnasse
    "Q2921894": ("Q90", "street", "Paris"),  # boulevard Pereire
    "Q3447053": ("Q90", "street", "Paris"),  # rue Ballu
    "Q3447168": ("Q90", "street", "Paris"),  # rue Blanche
    "Q3447453": ("Q90", "street", "Paris"),  # rue Christophe-Colomb
    "Q3447626": ("Q90", "street", "Paris"),  # rue Dauphine
    "Q3450713": ("Q90", "street", "Paris"),  # rue de Douai
    "Q1640681": ("Q90", "street", "Paris"),  # rue de la Chaussée-d'Antin
    "Q3451594": ("Q90", "street", "Paris"),  # rue de la Verrerie
    "Q48748327": ("Q90", "street", "Paris"),  # Rue d'Enfer
    "Q3451060": ("Q90", "street", "Paris"),  # rue de Steinkerque
    "Q3452235": ("Q90", "street", "Paris"),  # rue du Conservatoire
    "Q2378296": ("Q90", "street", "Paris"),  # rue Louise-Émilie-de-La-Tour-d'Auvergne
    "Q3449529": ("Q90", "street", "Paris"),  # rue Pierre-Larousse
    "Q3449728": ("Q90", "street", "Paris"),  # rue Richer
    "Q1356926": ("Q90", "street", "Paris"),  # rue Saint-Jacques
    "Q3450116": ("Q90", "street", "Paris"),  # rue Taitbout
    "Q3450316": ("Q90", "street", "Paris"),  # rue Victor-Massé
    "Q137475146": ("Q42810", "street", "Le Havre"),  # Rue Robert de la Villehervé (NOT Paris -- verified via Wikidata P131)
    "Q24929623": ("Q48958", "street", "Neuilly-sur-Seine"),  # Boulevard d'Inkermann (NOT Paris -- verified via Wikidata P131)
    "Q3452020": ("Q3992", "street", "Liège"),  # Rue des Récollets (NOT Paris -- verified via Wikidata P131)
    "Q22249019": ("Q30974", "street", "Rouen"),  # Rue aux Ours, Rouen (own name already says Rouen; place_link's substring guard avoids "Rouen, Rouen")

    # Church parishes (mostly Swedish, one Danish, one French -- found
    # 2026-09-14 via swedishmusicalheritage.com composers: Sweden's church
    # ran civil registration until 1991, kept per-parish rather than
    # per-city, so a composer's birth/death place is very often recorded
    # at parish granularity, e.g. "Katarina church parish" rather than
    # "Stockholm"). Verified one parish at a time against Wikidata's own
    # P131 ("located in the administrative territorial entity") or P3842
    # ("present-day administrative territorial entity", used on dissolved
    # parishes) claim -- which for Sweden almost always points at the
    # enclosing *kommun* (municipality) rather than a separate "locality"
    # entity, e.g. "Stockholm Municipality" (Q506250), not plain
    # "Stockholm" (Q1754). Where this repo already tracked the city under
    # its own QID, that's the target used here, matching how the city
    # would be referenced directly by any other composer's birth/death
    # place. Where no separate settlement row existed at all (most of the
    # smaller towns: Täby, Filipstad, Nacka, Västerås, ...), the
    # municipality's own QID is used as a pragmatic settlement stand-in --
    # for these smaller places the kommun and the town share a name and
    # are colloquially the same place for display purposes; same
    # reasoning applied to Lyne Parish's Ringkøbing-Skjern Municipality
    # (Denmark) below, no separate village-level QID exists for Lyne
    # itself either.
    "Q3433770": ("Q1754", "parish", "Stockholm"),  # Adolf Fredriks parish
    "Q10726031": ("Q25286", "parish", "Uppsala"),  # Ärentuna parish
    "Q10419791": ("Q25732", "parish", "Örebro"),  # Asker parish
    "Q10436974": ("Q1754", "parish", "Stockholm"),  # Brännkyrka parish
    "Q10437862": ("Q186662", "parish", "Burlöv"),  # Burlövs parish
    "Q10475816": ("Q25287", "parish", "Gothenburg"),  # Domkyrkoförsamlingen in Göteborg
    "Q10484135": ("Q1754", "parish", "Stockholm"),  # Engelbrekt church parish
    "Q10489189": ("Q1754", "parish", "Stockholm"),  # Essinge church parish
    "Q10493877": ("Q26509", "parish", "Falun"),  # Falu Kristine church parish
    "Q10500869": ("Q498857", "parish", "Kristianstad"),  # Färlöv parish
    "Q10495152": ("Q503204", "parish", "Filipstad"),  # Filipstad church parish
    "Q10501931": ("Q2642771", "parish", "Gagnef"),  # Gagnef parish
    "Q10512443": ("Q25748", "parish", "Gävle"),  # Gävle Staffan church parish
    "Q10512805": ("Q25287", "parish", "Gothenburg"),  # Göteborgs Carl Johans parish
    "Q10512824": ("Q25287", "parish", "Gothenburg"),  # Göteborgs Kristine församling
    "Q10511165": ("Q1754", "parish", "Stockholm"),  # Gustav Vasa parish
    "Q10531820": ("Q508125", "parish", "Hässleholm"),  # Hässleholm church parish
    "Q10519255": ("Q1754", "parish", "Stockholm"),  # Hedvig Eleonora parish
    "Q10520535": ("Q25411", "parish", "Helsingborg"),  # Helsingborgs Maria church parish
    "Q10526862": ("Q29963", "parish", "Hudiksvall"),  # Hudiksvall parish
    "Q54006791": ("Q1754", "parish", "Stockholm"),  # Jakob and Johannes parish
    "Q10541678": ("Q504257", "parish", "Olofström"),  # Jämshög church parish
    "Q10540465": ("Q25287", "parish", "Gothenburg"),  # Johannebergs församling
    "Q10542102": ("Q25415", "parish", "Jönköping"),  # Jönköpings Kristina församling
    "Q10543836": ("Q510223", "parish", "Karlshamn"),  # Karlshamn church parish
    "Q10543883": ("Q25789", "parish", "Karlskrona"),  # Karlskrona tyska församling
    "Q10543924": ("Q25457", "parish", "Karlstad"),  # Karlstad church parish
    "Q3427889": ("Q1754", "parish", "Stockholm"),  # Katarina church parish
    "Q10545818": ("Q515299", "parish", "Kinda"),  # Kisa församling
    "Q10546040": ("Q1754", "parish", "Stockholm"),  # Klara Church Parish
    "Q10546691": ("Q504465", "parish", "Knivsta"),  # Knivsta församling
    "Q10549260": ("Q510364", "parish", "Kristinehamn"),  # Kristinehamns församling
    "Q10550317": ("Q1754", "parish", "Stockholm"),  # Kungsholm parish
    "Q10556731": ("Q509651", "parish", "Leksand"),  # Leksands parish
    "Q10561393": ("Q515358", "parish", "Lidköping"),  # Lidköping parish
    "Q10570835": ("Q2167", "parish", "Lund"),  # Lund Cathedral parish
    "Q10576133": ("Q2211", "parish", "Malmö"),  # Malmö Sankt Petri församling
    "Q3438210": ("Q1754", "parish", "Stockholm"),  # Maria Magdalena parish
    "Q18292494": ("Q946647", "parish", "Nacka"),  # Nacka församling
    "Q10601893": ("Q285894", "parish", "Nora"),  # Nora mountain parish
    "Q18292588": ("Q508125", "parish", "Hässleholm"),  # Norra Mellby church parish
    "Q10602574": ("Q654299", "parish", "Nässjö"),  # Norra Solberga church parish
    "Q10602802": ("Q10602808", "parish", "Norrköping"),  # Norrköping Matteus church parish
    "Q10727562": ("Q25287", "parish", "Gothenburg"),  # Örgryte församling
    "Q10611872": ("Q113692", "parish", "Haninge"),  # Ornö Parish
    "Q10612957": ("Q25287", "parish", "Gothenburg"),  # Oscar Fredriks församling
    "Q10612973": ("Q1754", "parish", "Stockholm"),  # Oscar Parish
    "Q10727852": ("Q54757", "parish", "Visby"),  # Östergarn parish
    "Q10728033": ("Q113692", "parish", "Haninge"),  # Österhaninge church parish
    "Q10613434": ("Q515358", "parish", "Lidköping"),  # Otterstads församling
    "Q10707814": ("Q1754", "parish", "Stockholm"),  # Parish of St Gertrud of Germany
    "Q10658365": ("Q34550", "parish", "Västerås"),  # Rytterne församling
    "Q10687878": ("Q505071", "parish", "Tranås"),  # Säby församling, Linköpings stift
    "Q97293132": ("Q90", "parish", "Paris"),  # Saint-Sulpice parish
    "Q10661183": ("Q894327", "parish", "Borås"),  # Sandhults församling
    "Q10671306": ("Q501452", "parish", "Skövde"),  # Skövde Parish
    "Q10671779": ("Q499380", "parish", "Kungsbacka"),  # Släps församling
    "Q10672766": ("Q505102", "parish", "Ystad"),  # Snårestads parish
    "Q10688543": ("Q145835", "parish", "Söderhamn"),  # Söderhamn parish
    "Q10673010": ("Q1754", "parish", "Stockholm"),  # Sofia church parish
    "Q10673099": ("Q511394", "parish", "Kungälv"),  # Solberga parish
    "Q18560570": ("Q503746", "parish", "Sollentuna"),  # Sollentuna parish
    "Q10659387": ("Q1754", "parish", "Stockholm"),  # S:t Görans church parish
    "Q10680577": ("Q1754", "parish", "Stockholm"),  # Stockholm Cathedral Parish
    "Q10681037": ("Q26509", "parish", "Falun"),  # Stora Kopparberg parish
    "Q43549106": ("Q1754", "parish", "Stockholm"),  # Storkyrkoförsamlingen
    "Q10683835": ("Q504994", "parish", "Sundsvall"),  # Sundsvalls parish
    "Q31899080": ("Q1754", "parish", "Stockholm"),  # Svea livgardes church parish
    "Q10684655": ("Q513421", "parish", "Härjedalen"),  # Svegs församling
    "Q10707908": ("Q493066", "parish", "Täby"),  # Täby parish
    "Q10526665": ("Q1754", "parish", "Stockholm"),  # The Royal Court Parish
    "Q10698211": ("Q504983", "parish", "Timrå"),  # Timrå församling
    "Q10700451": ("Q54341", "parish", "Borlänge"),  # Torsångs församling
    "Q10711974": ("Q515969", "parish", "Vadstena"),  # Vadstena church församling
    "Q18334839": ("Q511426", "parish", "Vänersborg"),  # Vänersborg Parish
    "Q10712701": ("Q1754", "parish", "Stockholm"),  # Vantörs parish
    "Q11055413": ("Q26518", "parish", "Södertälje"),  # Vårdinge church parish
    "Q10713238": ("Q25287", "parish", "Gothenburg"),  # Vasa parish
    "Q10718088": ("Q34550", "parish", "Västerås"),  # Västerås domkyrkoförsamling
    "Q10718036": ("Q515477", "parish", "Västervik"),  # Västerviks church parish
    "Q10718570": ("Q26152", "parish", "Växjö"),  # Växjö Parish
    "Q10715396": ("Q515861", "parish", "Vilhelmina"),  # Vilhelmina church parish
    "Q10716051": ("Q54757", "parish", "Visby"),  # Visby parish
    "Q2100818": ("Q514777", "parish", "Ringkøbing-Skjern"),  # Lyne Parish (Denmark)
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

            for landmark_qid, (settlement_qid, place_type, settlement_name) in LANDMARK_LOCATIONS.items():
                landmark_id = _place_id_for_qid(cur, landmark_qid)
                if landmark_id is None:
                    print(f"skip {landmark_qid} -> {settlement_qid}: landmark not yet tracked")
                    continue
                settlement_id = _place_id_for_qid(cur, settlement_qid)
                if settlement_id is None:
                    # Most of the smaller towns among the parishes: never
                    # referenced as a settlement in their own right by any
                    # composer's birth/death place directly, only reachable
                    # through their parish -- create the row here rather
                    # than skip, unlike every other dict in this file (which
                    # assumes the target already exists via
                    # load_birth_death_places.py).
                    cur.execute("INSERT INTO places (name) VALUES (%s) RETURNING id", (settlement_name,))
                    settlement_id = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO place_qids (place_id, wikidata_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (settlement_id, settlement_qid),
                    )
                cur.execute(
                    "UPDATE places SET place_type=%s, located_in_place_id=%s WHERE id=%s",
                    (place_type, settlement_id, landmark_id),
                )

    conn.close()
    print("done")


if __name__ == "__main__":
    main()

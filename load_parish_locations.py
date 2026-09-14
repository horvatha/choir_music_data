"""Set places.located_in_place_id for Swedish (and a couple of Danish/
French) church parishes -- the standard place unit in older Swedish
biographical/genealogical records, e.g. Wikidata's own P569/P570 place
claims often point at a parish like "Katarina church parish" rather than
the city it's in ("Stockholm"), which was showing on composer pages with
no settlement name at all. Same underlying gap and fix shape as
load_place_hierarchy.py's LANDMARK_LOCATIONS (streets -> Paris), just a
different landmark category (a parish also has no local government of
its own) -- kept in its own file/dict rather than folded into
LANDMARK_LOCATIONS since the two were found and verified in separate
passes and there's no benefit to merging them.

Found via swedishmusicalheritage.com composers (Gunno Södersten's
"Katarina church parish, Sweden" birthplace showing no settlement),
then swept across every composer birth/death place already in the DB
that matched "%parish%"/"%församling%" with no located_in_place_id or
parent_place_id set: 84 places, 130 composer birth/death references.

Each entry below is (target settlement's Wikidata QID, target name),
verified one parish at a time against Wikidata's own P131 ("located in
the administrative territorial entity") or P3842 ("present-day
administrative territorial entity", used on dissolved parishes) claim --
which for Sweden almost always points at the enclosing *kommun*
(municipality) rather than a separate "locality" entity, e.g. "Stockholm
Municipality" (Q506250), not plain "Stockholm" (Q1754). Where this repo
already tracked the city under its own QID, that's the target used here
(Q1754 for Stockholm, not Q506250) -- matching how the city would be
referenced directly by any other composer's birth/death place. Where no
separate settlement row existed at all (most of the smaller towns:
Täby, Filipstad, Nacka, Västerås, ...), a new place row is created here,
backed by the municipality's own QID directly -- pragmatic rather than
hunting down each town's separate "locality" QID individually, since for
these smaller places the kommun and the town share a name and are
colloquially the same place for display purposes.

One parish (Lyne Parish, Q2100818 -- Ringkøbing-Skjern Municipality,
Denmark; composer id 2598, Morten Eskesen) is deliberately NOT included
here: it didn't fit this batch's Swedish-municipality-name pattern and
needs its own separate look at an actual Danish settlement-level QID.

Safe to rerun: every UPDATE/INSERT here is idempotent (INSERT ... ON
CONFLICT DO NOTHING for the place_qids row of a newly-created
settlement; the located_in_place_id UPDATE is unconditional but always
converges to the same value).

Usage:
    python3 load_parish_locations.py
"""
import psycopg2

# parish_qid -> (settlement_qid, settlement_name)
PARISH_LOCATIONS = {
    "Q3433770": ("Q1754", "Stockholm"),  # Adolf Fredriks parish
    "Q10726031": ("Q25286", "Uppsala"),  # Ärentuna parish
    "Q10419791": ("Q25732", "Örebro"),  # Asker parish
    "Q10436974": ("Q1754", "Stockholm"),  # Brännkyrka parish
    "Q10437862": ("Q186662", "Burlöv"),  # Burlövs parish
    "Q10475816": ("Q25287", "Gothenburg"),  # Domkyrkoförsamlingen in Göteborg
    "Q10484135": ("Q1754", "Stockholm"),  # Engelbrekt church parish
    "Q10489189": ("Q1754", "Stockholm"),  # Essinge church parish
    "Q10493877": ("Q26509", "Falun"),  # Falu Kristine church parish
    "Q10500869": ("Q498857", "Kristianstad"),  # Färlöv parish
    "Q10495152": ("Q503204", "Filipstad"),  # Filipstad church parish
    "Q10501931": ("Q2642771", "Gagnef"),  # Gagnef parish
    "Q10512443": ("Q25748", "Gävle"),  # Gävle Staffan church parish
    "Q10512805": ("Q25287", "Gothenburg"),  # Göteborgs Carl Johans parish
    "Q10512824": ("Q25287", "Gothenburg"),  # Göteborgs Kristine församling
    "Q10511165": ("Q1754", "Stockholm"),  # Gustav Vasa parish
    "Q10531820": ("Q508125", "Hässleholm"),  # Hässleholm church parish
    "Q10519255": ("Q1754", "Stockholm"),  # Hedvig Eleonora parish
    "Q10520535": ("Q25411", "Helsingborg"),  # Helsingborgs Maria church parish
    "Q10526862": ("Q29963", "Hudiksvall"),  # Hudiksvall parish
    "Q54006791": ("Q1754", "Stockholm"),  # Jakob and Johannes parish
    "Q10541678": ("Q504257", "Olofström"),  # Jämshög church parish
    "Q10540465": ("Q25287", "Gothenburg"),  # Johannebergs församling
    "Q10542102": ("Q25415", "Jönköping"),  # Jönköpings Kristina församling
    "Q10543836": ("Q510223", "Karlshamn"),  # Karlshamn church parish
    "Q10543883": ("Q25789", "Karlskrona"),  # Karlskrona tyska församling
    "Q10543924": ("Q25457", "Karlstad"),  # Karlstad church parish
    "Q3427889": ("Q1754", "Stockholm"),  # Katarina church parish
    "Q10545818": ("Q515299", "Kinda"),  # Kisa församling
    "Q10546040": ("Q1754", "Stockholm"),  # Klara Church Parish
    "Q10546691": ("Q504465", "Knivsta"),  # Knivsta församling
    "Q10549260": ("Q510364", "Kristinehamn"),  # Kristinehamns församling
    "Q10550317": ("Q1754", "Stockholm"),  # Kungsholm parish
    "Q10556731": ("Q509651", "Leksand"),  # Leksands parish
    "Q10561393": ("Q515358", "Lidköping"),  # Lidköping parish
    "Q10570835": ("Q2167", "Lund"),  # Lund Cathedral parish
    "Q10576133": ("Q2211", "Malmö"),  # Malmö Sankt Petri församling
    "Q3438210": ("Q1754", "Stockholm"),  # Maria Magdalena parish
    "Q18292494": ("Q946647", "Nacka"),  # Nacka församling
    "Q10601893": ("Q285894", "Nora"),  # Nora mountain parish
    "Q18292588": ("Q508125", "Hässleholm"),  # Norra Mellby church parish
    "Q10602574": ("Q654299", "Nässjö"),  # Norra Solberga church parish
    "Q10602802": ("Q10602808", "Norrköping"),  # Norrköping Matteus church parish
    "Q10727562": ("Q25287", "Gothenburg"),  # Örgryte församling
    "Q10611872": ("Q113692", "Haninge"),  # Ornö Parish
    "Q10612957": ("Q25287", "Gothenburg"),  # Oscar Fredriks församling
    "Q10612973": ("Q1754", "Stockholm"),  # Oscar Parish
    "Q10727852": ("Q54757", "Visby"),  # Östergarn parish
    "Q10728033": ("Q113692", "Haninge"),  # Österhaninge church parish
    "Q10613434": ("Q515358", "Lidköping"),  # Otterstads församling
    "Q10707814": ("Q1754", "Stockholm"),  # Parish of St Gertrud of Germany
    "Q10658365": ("Q34550", "Västerås"),  # Rytterne församling
    "Q10687878": ("Q505071", "Tranås"),  # Säby församling, Linköpings stift
    "Q97293132": ("Q90", "Paris"),  # Saint-Sulpice parish
    "Q10661183": ("Q894327", "Borås"),  # Sandhults församling
    "Q10671306": ("Q501452", "Skövde"),  # Skövde Parish
    "Q10671779": ("Q499380", "Kungsbacka"),  # Släps församling
    "Q10672766": ("Q505102", "Ystad"),  # Snårestads parish
    "Q10688543": ("Q145835", "Söderhamn"),  # Söderhamn parish
    "Q10673010": ("Q1754", "Stockholm"),  # Sofia church parish
    "Q10673099": ("Q511394", "Kungälv"),  # Solberga parish
    "Q18560570": ("Q503746", "Sollentuna"),  # Sollentuna parish
    "Q10659387": ("Q1754", "Stockholm"),  # S:t Görans church parish
    "Q10680577": ("Q1754", "Stockholm"),  # Stockholm Cathedral Parish
    "Q10681037": ("Q26509", "Falun"),  # Stora Kopparberg parish
    "Q43549106": ("Q1754", "Stockholm"),  # Storkyrkoförsamlingen
    "Q10683835": ("Q504994", "Sundsvall"),  # Sundsvalls parish
    "Q31899080": ("Q1754", "Stockholm"),  # Svea livgardes church parish
    "Q10684655": ("Q513421", "Härjedalen"),  # Svegs församling
    "Q10707908": ("Q493066", "Täby"),  # Täby parish
    "Q10526665": ("Q1754", "Stockholm"),  # The Royal Court Parish
    "Q10698211": ("Q504983", "Timrå"),  # Timrå församling
    "Q10700451": ("Q54341", "Borlänge"),  # Torsångs församling
    "Q10711974": ("Q515969", "Vadstena"),  # Vadstena church församling
    "Q18334839": ("Q511426", "Vänersborg"),  # Vänersborg Parish
    "Q10712701": ("Q1754", "Stockholm"),  # Vantörs parish
    "Q11055413": ("Q26518", "Södertälje"),  # Vårdinge church parish
    "Q10713238": ("Q25287", "Gothenburg"),  # Vasa parish
    "Q10718088": ("Q34550", "Västerås"),  # Västerås domkyrkoförsamling
    "Q10718036": ("Q515477", "Västervik"),  # Västerviks church parish
    "Q10718570": ("Q26152", "Växjö"),  # Växjö Parish
    "Q10715396": ("Q515861", "Vilhelmina"),  # Vilhelmina church parish
    "Q10716051": ("Q54757", "Visby"),  # Visby parish
}


def _place_id_for_qid(cur, qid):
    cur.execute("SELECT place_id FROM place_qids WHERE wikidata_id = %s", (qid,))
    row = cur.fetchone()
    return row[0] if row else None


def main():
    conn = psycopg2.connect()
    conn.autocommit = True
    updated = 0
    created = 0
    skipped = []
    try:
        with conn.cursor() as cur:
            for parish_qid, (settlement_qid, settlement_name) in PARISH_LOCATIONS.items():
                parish_id = _place_id_for_qid(cur, parish_qid)
                if parish_id is None:
                    skipped.append((parish_qid, settlement_name, "parish not yet tracked"))
                    continue

                settlement_id = _place_id_for_qid(cur, settlement_qid)
                if settlement_id is None:
                    cur.execute("INSERT INTO places (name) VALUES (%s) RETURNING id", (settlement_name,))
                    settlement_id = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO place_qids (place_id, wikidata_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (settlement_id, settlement_qid),
                    )
                    created += 1

                cur.execute(
                    "UPDATE places SET place_type='parish', located_in_place_id=%s WHERE id=%s",
                    (settlement_id, parish_id),
                )
                updated += 1
    finally:
        conn.close()

    print(f"Linked {updated} parishes to their settlement ({created} new settlement place rows created).")
    if skipped:
        print(f"Skipped ({len(skipped)}):")
        for qid, name, reason in skipped:
            print(f"  {qid} -> {name}: {reason}")


if __name__ == "__main__":
    main()

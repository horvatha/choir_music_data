"""Consolidates this repo's tag/movement (Wikidata P135) curation rules --
which raw claim QIDs are real, usable movement concepts, what a tag should
be named, and which composer/tag pairs Wikidata itself is missing -- as
opposed to the mechanics of fetching (adapters/wikidata_api.py) or
storing (load_tags.py's SQL) them. Every function here is pure: plain
Python values in, plain Python values out. load_tags.py does its own
cache-shape reading (entry["attributes"]["movement"]) and all the DB
writes, then hands off the "what tags should this actually become"
decision to this module.

See schema.sql's comment on the tags table for why this repo calls
Wikidata's "movement" property "tags" instead.
"""

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
    "Q21662779",  # Neue Musik -- German-language synonym for "contemporary
                  # classical music"/"contemporary music" above, not a named
                  # school with a defined membership (Wikidata's own
                  # description: "collective term for a vast number of
                  # different currents... from about 1910 to the present").
                  # Only Wolfgang Rihm carried it; no defensible backfill
                  # target the way First Viennese School/Biedermeier had.

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

# composers.wikidata_id -> [tags.wikidata_id, ...] -- hand-added
# composer/tag associations for real, named schools/movements found via a
# full tag-review pass (choir_music_data's reports/tags_review.md,
# gitignored, not committed) where Wikidata itself simply has no P135
# claim at all for a composer who's a documented member -- e.g. none of
# Haydn/Mozart/Beethoven have a "First Viennese School" P135 claim,
# despite it being close to the definition of the term. Full sourcing
# per composer/tag pair is in wikidata_changes/tags_missing_p135_backfill.wiki.
#
# Applied automatically after the normal Wikidata-claim pass in
# load_tags.py, since that script TRUNCATEs both tags and composer_tags on
# every run -- an earlier version of this fix was a raw, undocumented psql
# patch applied once by hand, which got silently wiped the very next time
# load_tags.py ran (triggered by adding one new composer, Ramón Barce, to
# Generación del 51) and had to be reconstructed from scratch. Keyed by
# wikidata_id on both sides (not internal ids) because TRUNCATE ...
# RESTART IDENTITY resets every tag's own id on every run -- same
# self-healing pattern as load_place_period_names.py's
# MANUAL_PERIOD_NAMES. Includes a handful of composer/tag pairs that also
# have a genuine Wikidata claim (harmless duplication via ON CONFLICT DO
# NOTHING -- simpler than maintaining two separate lists).
MANUAL_COMPOSER_TAGS = {
    "Q1093593": ['Q704073'],  # Antonio Zacara da Teramo -- ars subtilior
    "Q1254597": ['Q5303621'],  # Richard Maxfield -- Downtown music
    "Q1268": ['Q154432'],  # Frédéric Chopin -- Biedermeier
    "Q1277459": ['Q1972942'],  # Earle Brown -- New York School
    "Q1406473": ['Q615418'],  # Witold Rudziński -- sonorism
    "Q143059": ['Q185858'],  # Johannes Ockeghem -- Franco-Flemish School
    "Q143100": ['Q185858'],  # Josquin des Prez -- Franco-Flemish School
    "Q153469": ['Q615418'],  # Krzysztof Penderecki -- sonorism
    "Q154770": ['Q1362030', 'Q248243', 'Q507246', 'Q221686'],  # Arnold Schoenberg -- Second Viennese School, expressionism, serialism, twelve-tone technique
    "Q154792": ['Q185858'],  # Orlande de Lassus -- Franco-Flemish School
    "Q154812": ['Q154432'],  # Carl Maria von Weber -- Biedermeier
    "Q15520837": ['Q5303621'],  # Elodie Lauten -- Downtown music
    "Q156472": ['Q615418'],  # Witold Lutosławski -- sonorism
    "Q1664987": ['Q507246'],  # Jan Klusák -- serialism
    "Q1720016": ['Q615418'],  # Kazimierz Serocki -- sonorism
    "Q1775599": ['Q704073'],  # Trebor -- ars subtilior
    "Q180026": ['Q163491'],  # Petrus de Cruce -- ars antiqua
    "Q1800718": ['Q131784556'],  # Ludomir Różycki -- młoda polska
    "Q180727": ['Q1972942'],  # John Cage -- New York School
    "Q189534": ['Q572901'],  # Arvo Pärt -- minimalist music
    "Q189729": ['Q5303621'],  # Philip Glass -- Downtown music
    "Q190933": ['Q1362030', 'Q248243', 'Q507246', 'Q221686'],  # Anton Webern -- Second Viennese School, expressionism, serialism, twelve-tone technique
    "Q1947131": ['Q3100481'],  # Ramón Barce -- Generación del 51
    "Q1988679": ['Q185858'],  # Arnold de Lantins -- Franco-Flemish School
    "Q206275": ['Q163491', 'Q830881'],  # Pérotin (Perotinus) -- Notre Dame school, ars antiqua
    "Q207390": ['Q1935489'],  # Amilcare Ponchielli -- Scapigliatura
    "Q207717": ['Q2007658'],  # Guillaume Dufay (Guillaume Du Fay) -- Burgundian School
    "Q2116807": ['Q704073'],  # Johannes CuvelierJean; Jacquemart le Cuvelier -- ars subtilior
    "Q214964": ['Q2007658'],  # Gilles Binchois (Gilles de Bins) -- Burgundian School
    "Q219491": ['Q1935489'],  # Arrigo Boito -- Scapigliatura
    "Q2202999": ['Q185858'],  # Johannes Martini -- Franco-Flemish School
    "Q2265181": ['Q704073'],  # Philippus de Caserta (Philipoctus de Caserta) -- ars subtilior
    "Q230978": ['Q615418'],  # Grażyna Bacewicz -- sonorism
    "Q2343880": ['Q704073'],  # Matteo da Perugia -- ars subtilior
    "Q235066": ['Q5303621'],  # Laurie Anderson -- Downtown music
    "Q245348": ['Q615418'],  # Zygmunt Krauze -- sonorism
    "Q254": ['Q702207'],  # Wolfgang Amadeus Mozart -- First Viennese School
    "Q255": ['Q702207', 'Q154432'],  # Ludwig van Beethoven -- First Viennese School, Biedermeier
    "Q2602845": ['Q3100481'],  # Carmelo Bernaola -- Generación del 51
    "Q2617839": ['Q3100481'],  # Luis de Pablo -- Generación del 51
    "Q2622143": ['Q615418'],  # Andrzej Dobrowolski -- sonorism
    "Q262791": ['Q5303621'],  # Steve Reich -- Downtown music
    "Q277029": ['Q185858'],  # Philippe de Monte -- Franco-Flemish School
    "Q28480": ['Q1362030'],  # Max Brod -- expressionism
    "Q286273": ['Q185858'],  # Balduin Hoyoul -- Franco-Flemish School
    "Q294568": ['Q572901', 'Q615418'],  # Henryk Górecki -- minimalist music, sonorism
    "Q295400": ['Q131784556'],  # Karol Szymanowski -- młoda polska
    "Q297501": ['Q163491', 'Q830881'],  # Léonin -- Notre Dame school, ars antiqua
    "Q298726": ['Q5303621'],  # John Zorn -- Downtown music
    "Q3018260": ['Q5303621'],  # David Lang -- Downtown music
    "Q3038778": ['Q3100481'],  # Joan Guinjoan -- Generación del 51
    "Q312615": ['Q185858'],  # Adrian Willaert -- Franco-Flemish School
    "Q314019": ['Q702207'],  # Ignaz Pleyel -- First Viennese School
    "Q316427": ['Q1972942', 'Q5303621'],  # Morton Feldman -- Downtown music, New York School
    "Q317350": ['Q572901'],  # John Tavener -- minimalist music
    "Q317937": ['Q2007658'],  # Antoine Busnois -- Burgundian School
    "Q3184122": ['Q3100481'],  # Josep Soler i Sardà -- Generación del 51
    "Q319777": ['Q615418'],  # Wojciech Kilar -- sonorism
    "Q324253": ['Q989478'],  # Johann Gottlieb Janitsch -- empfindsamkeit
    "Q327040": ['Q572901'],  # Hans Otte -- minimalist music
    "Q3308220": ['Q5303621'],  # Michael Gordon -- Downtown music
    "Q352722": ['Q1935489'],  # Alfredo Catalani -- Scapigliatura
    "Q370512": ['Q185858'],  # Johannes Tinctoris -- Franco-Flemish School
    "Q375388": ['Q3100481'],  # Cristóbal Halffter -- Generación del 51
    "Q376521": ['Q163491'],  # Albertus Parisiensis -- ars antiqua
    "Q378148": ['Q704073'],  # Johannes Ciconia -- ars subtilior
    "Q3847499": ['Q3100481'],  # Tomás Marco -- Generación del 51
    "Q386172": ['Q704073'],  # Jacob Senleches -- ars subtilior
    "Q41309": ['Q154432'],  # Franz Liszt -- Biedermeier
    "Q432299": ['Q702207'],  # Johann Adam Hiller -- First Viennese School
    "Q432822": ['Q5303621'],  # La Monte Young -- Downtown music
    "Q433661": ['Q5303621'],  # Glenn Branca -- Downtown music
    "Q438090": ['Q185858'],  # Jacob Clemens non Papa -- Franco-Flemish School
    "Q452352": ['Q248243'],  # Nikos Skalkottas -- Second Viennese School
    "Q45909": ['Q5303621'],  # John Cale -- Downtown music
    "Q46096": ['Q154432'],  # Felix Mendelssohn -- Biedermeier
    "Q465396": ['Q615418'],  # Bogusław Schaeffer -- sonorism
    "Q508891": ['Q131784556'],  # Mieczysław Karłowicz -- młoda polska
    "Q514391": ['Q704073'],  # Paolo da Firenze (Paolo Tenorista) -- ars subtilior
    "Q545594": ['Q615418'],  # Tadeusz Baird -- sonorism
    "Q554780": ['Q5303621'],  # Rhys Chatham -- Downtown music
    "Q610544": ['Q3100481'],  # Antón García Abril -- Generación del 51
    "Q6306853": ['Q5303621'],  # Julia Wolfe -- Downtown music
    "Q631120": ['Q704073'],  # Solage -- ars subtilior
    "Q642456": ['Q185858'],  # Philippe Rogier -- Franco-Flemish School
    "Q652558": ['Q615418'],  # Krzysztof Meyer -- sonorism
    "Q658733": ['Q1972942'],  # Christian Wolff -- New York School
    "Q689576": ['Q702207'],  # Georg Matthias Monn -- First Viennese School
    "Q715624": ['Q615418'],  # Witold Szalonek -- sonorism
    "Q7311": ['Q1935489'],  # Giacomo Puccini -- Scapigliatura
    "Q7312": ['Q154432'],  # Franz Schubert -- Biedermeier
    "Q7314": ['Q507246', 'Q221686'],  # Igor Stravinsky -- serialism, twelve-tone technique
    "Q7349": ['Q702207'],  # Joseph Haydn -- First Viennese School
    "Q7351": ['Q154432'],  # Robert Schumann -- Biedermeier
    "Q76428": ['Q989478'],  # Carl Philipp Emanuel Bach -- empfindsamkeit
    "Q78475": ['Q1362030', 'Q248243', 'Q507246', 'Q221686'],  # Alban Berg -- Second Viennese School, expressionism, serialism, twelve-tone technique
    "Q8008040": ['Q5303621'],  # William Duckworth -- Downtown music
    "Q86359": ['Q221686'],  # Josef Matthias Hauer -- twelve-tone technique
    "Q9726": ['Q154432'],  # Gioachino Rossini -- Biedermeier
    "Q975576": ['Q185858'],  # Loyset Compère -- Franco-Flemish School
    "Q983103": ['Q131784556'],  # Grzegorz Fitelberg -- młoda polska
}


def resolve_tag_qids(raw_qids: list[str]) -> list[str]:
    """Turn one composer's raw P135 claim QIDs into the QIDs that should
    actually become tags: QID_REDIRECTS applied first (a mistagged value
    silently corrected), then anything left in EXCLUDED_QIDS dropped."""
    result = []
    for qid in raw_qids:
        qid = QID_REDIRECTS.get(qid, qid)
        if qid in EXCLUDED_QIDS:
            continue
        result.append(qid)
    return result


def resolve_tag_name(qid: str, qid_labels: dict[str, str]) -> str:
    """NAME_OVERRIDES first (a label collision this repo already knows
    about), else whatever qid_labels resolved to (see get_labels() in
    adapters/wikidata_api.py), else the bare QID as a last resort -- no
    label was ever fetched for this tag at all."""
    return NAME_OVERRIDES.get(qid, qid_labels.get(qid, qid))

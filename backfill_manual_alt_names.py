"""Load a small set of hand-constructed composer_alt_names entries that
aren't sourced from Wikidata at all -- unlike every other load_*/fetch_*
script in this repo, these are translations *we* wrote, not values pulled
from an API. Exists purely so they're reproducible (committed to git,
rerunnable after a schema reset) rather than living only as one-off SQL
run against the live DB, which is how they were first added.

Two groups:

1. ELDER_YOUNGER_DISAMBIGUATION -- Thomas Linley and Samuel Webbe each
   have an "the elder"/"the younger" composer pair in this DB. Wikidata's
   own labels for several languages just give both siblings the identical
   plain name (e.g. both Samuel Webbes are "Samuel Webbe" in German and
   Spanish) -- genuinely ambiguous once composers.name's English "the
   elder"/"the younger" qualifier isn't there to disambiguate. Follows
   whichever elder/younger convention Wikidata itself already uses
   elsewhere in this DB for the same language (e.g. German "der Ältere"/
   "der Jüngere" from the Ferrabosco pair, Polish "(starszy)"/"(młodszy)"
   from the same pair) or, absent that, each language's standard
   equivalent.

2. ROYALTY_GAPS -- a few remaining gaps for composers in the curated
   royalty/nobility fetch (see fetch_curated_composer_names.py) where
   Wikidata has no label at all in a target language, filled by mirroring
   an already-Wikidata-sourced pattern for the same person or a close
   relative in this dataset (e.g. Prince Gustaf of Sweden's Croatian name
   mirrors his relative Oscar I of Sweden's Wikidata-sourced Croatian
   "Oskar I. Švedski"). Deliberately *not* exhaustive -- several other
   gaps in the same set were left blank rather than guessed (e.g.
   Croatian for Anna Amalia of Saxe-Weimar-Eisenach or Princess
   Wilhelmine of Prussia) because there was no directly analogous,
   verified example to mirror, just a same-family-of-languages spelling
   guess -- see e.g. Frederick the Great's own Czech "Fridrich" vs
   Croatian "Fridrik" for why that's not safe to extrapolate from.

Usage:
    python3 backfill_manual_alt_names.py
"""
import psycopg2

# (composer_id, language) -> name. One block per person/pair; see each
# comment for the disambiguation this covers.
ELDER_YOUNGER_DISAMBIGUATION = {
    # Samuel Webbe the elder (1829) / the younger (2009) -- Wikidata gives
    # both the bare "Samuel Webbe" in de/es/hu/it/nl/ru (and, for fr/nl,
    # the younger only "the younger" in English, not translated).
    (1829, "de"): "Samuel Webbe der Ältere",
    (1829, "es"): "Samuel Webbe el Viejo",
    (1829, "fr"): "Samuel Webbe l'aîné",
    (1829, "hu"): "id. Samuel Webbe",
    (1829, "it"): "Samuel Webbe il Vecchio",
    (1829, "nl"): "Samuel Webbe de Oudere",
    (1829, "pl"): "Samuel Webbe (starszy)",
    (1829, "ru"): "Сэмюэл Уэбб старший",
    (1829, "cs"): "Samuel Webbe starší",
    (2009, "de"): "Samuel Webbe der Jüngere",
    (2009, "es"): "Samuel Webbe el Joven",
    (2009, "fr"): "Samuel Webbe le jeune",
    (2009, "hu"): "ifj. Samuel Webbe",
    (2009, "it"): "Samuel Webbe il Giovane",
    (2009, "nl"): "Samuel Webbe de Jongere",
    (2009, "pl"): "Samuel Webbe (młodszy)",
    (2009, "ru"): "Сэмюэл Уэбб младший",
    (2009, "cs"): "Samuel Webbe mladší",
    # Thomas Linley the elder (1795) / the younger (1930) -- de (senior/
    # junior) and fr (le Jeune, elder side only) already came from
    # Wikidata correctly disambiguated, so those two are left alone here.
    (1795, "es"): "Thomas Linley el Viejo",
    (1795, "fr"): "Thomas Linley l'aîné",
    (1795, "hu"): "id. Thomas Linley",
    (1795, "it"): "Thomas Linley il Vecchio",
    (1795, "nl"): "Thomas Linley de Oudere",
    (1795, "pl"): "Thomas Linley (starszy)",
    (1795, "ru"): "Томас Линли старший",
    (1795, "cs"): "Thomas Linley starší",
    (1930, "cs"): "Thomas Linley mladší",
    (1930, "es"): "Thomas Linley el Joven",
    (1930, "hu"): "ifj. Thomas Linley",
    (1930, "it"): "Thomas Linley il Giovane",
    (1930, "nl"): "Thomas Linley de Jongere",
    (1930, "pl"): "Thomas Linley (młodszy)",
    (1930, "ru"): "Томас Линли младший",
}

ROYALTY_GAPS = {
    # Princess Amalie of Saxony (2153) -- Wikidata's own "nl" label was
    # literally the untranslated English string ("Princess Amalie of
    # Saxony"), corrected here; hu/pl/hr had no Wikidata label at all,
    # filled following the "Name + regional adjective" pattern her
    # Prussian-princess relatives already use in this dataset (e.g.
    # Princess Wilhelmine of Prussia's Polish "Wilhelmina Pruska").
    (2153, "nl"): "Amalie van Saksen",
    (2153, "hu"): "Amália szász királyi hercegnő",
    (2153, "pl"): "Amalia Saska",
    (2153, "hr"): "Amalija Saska",
    # Prince Gustaf, Duke of Uppland (2256) -- Croatian mirrors his
    # relative Oscar I of Sweden's Wikidata-sourced Croatian "Oskar I.
    # Švedski" (same country, same "Name + Swedish adjective" pattern);
    # "Gustav" itself needs no spelling guess, it's already the same
    # across de/cs/ru for this person.
    (2256, "hr"): "Gustav Švedski",
}

UPSERT_ALT_NAME_SQL = """
    INSERT INTO composer_alt_names (composer_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (composer_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def load():
    entries = {**ELDER_YOUNGER_DISAMBIGUATION, **ROYALTY_GAPS}
    conn = psycopg2.connect()
    try:
        with conn:
            with conn.cursor() as cur:
                for (composer_id, language), name in entries.items():
                    cur.execute(UPSERT_ALT_NAME_SQL, (composer_id, language, name))
    finally:
        conn.close()
    print(f"Loaded {len(entries)} hand-constructed alt names "
          f"({len(ELDER_YOUNGER_DISAMBIGUATION)} elder/younger, {len(ROYALTY_GAPS)} royalty gaps).")


if __name__ == "__main__":
    load()

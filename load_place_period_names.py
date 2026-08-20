"""Load place_period_names(period_id, language, name) from the P1448
"official name" Wikidata claims fetch_place_history.py already cached in
wikidata_relationships.json's place_claims -- the same per-window data
load_birth_death_places.py's build_qid_windows() already reduces to ONE
canonical name per period (English > Russian > alphabetically-first) when
building place_periods.name/default_language. This backfills every other
language Wikidata actually has a period-scoped name for, not just the one
that won that tiebreak -- e.g. Saint Petersburg's 1924-1991 window gets
"Leningrad" (de), "Leningrád" (hu), "Ленінград" (uk/be), etc. alongside
place_periods.name's "Ленинград" (ru).

Must run after load_birth_death_places.py -- place_periods rows (with
real ids and start/end years) have to already exist. Safe to rerun: does
a full delete+reinsert per period touched, so a later Wikidata refetch
that adds/changes a language just replaces that period's row set instead
of accumulating stale entries.

A period's (start_year, end_year) window is always a sub-range of exactly
one raw P1448 window per language -- place_periods rows are built by
clipping/splitting raw Wikidata windows against country-claim boundaries,
never widening them (see merge_windows_to_periods() in
load_birth_death_places.py) -- so for each language we pick whichever raw
window most *tightly* contains the period's window as that language's
name for this period.

Usage:
    python3 load_place_period_names.py
"""
import psycopg2

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

# Stand-ins for open-ended ("None") window boundaries, wide enough that no
# real place_periods/P1448 year ever equals or crosses them -- lets the
# tightness comparison below use plain integer arithmetic instead of
# special-casing None on either side.
_NEG, _POS = -10 ** 9, 10 ** 9


def _bounds(start, end):
    return (_NEG if start is None else start), (_POS if end is None else end)


def _names_for_period(p1448, period_start, period_end):
    """{language: name} for whichever raw P1448 window most tightly
    contains (period_start, period_end), per language."""
    p_lo, p_hi = _bounds(period_start, period_end)
    best = {}  # language -> (span, name)
    for w in p1448:
        lo, hi = _bounds(w["start"], w["end"])
        if lo > p_lo or hi < p_hi:
            continue  # doesn't contain this period's window at all
        span = hi - lo
        language = w["language"]
        if language not in best or span < best[language][0]:
            best[language] = (span, w["name"])
    return {language: name for language, (span, name) in best.items()}


def load():
    data = load_cache(OUTPUT_FILE)
    place_claims = data.get("place_claims", {})

    conn = psycopg2.connect()
    loaded = 0
    periods_touched = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, place_id, start_year, end_year FROM place_periods")
                periods = cur.fetchall()

                cur.execute("SELECT place_id, wikidata_id FROM place_qids")
                qids_by_place = {}
                for place_id, qid in cur.fetchall():
                    qids_by_place.setdefault(place_id, []).append(qid)

                for period_id, place_id, start, end in periods:
                    names_by_language = {}
                    for qid in qids_by_place.get(place_id, []):
                        p1448 = place_claims.get(qid, {}).get("p1448", [])
                        if not p1448:
                            continue
                        # First QID in the cluster to have a language wins --
                        # only matters for a predecessor-chain place (e.g.
                        # Königsberg/Kaliningrad) where two different QIDs'
                        # own P1448 claims happen to share a language, which
                        # hasn't been observed in practice.
                        for language, name in _names_for_period(p1448, start, end).items():
                            names_by_language.setdefault(language, name)
                    if not names_by_language:
                        continue
                    cur.execute("DELETE FROM place_period_names WHERE period_id = %s", (period_id,))
                    for language, name in names_by_language.items():
                        cur.execute(
                            "INSERT INTO place_period_names (period_id, language, name) VALUES (%s, %s, %s)",
                            (period_id, language, name),
                        )
                        loaded += 1
                    periods_touched += 1
    finally:
        conn.close()
    print(f"Loaded {loaded} place period names across {periods_touched} periods.")


if __name__ == "__main__":
    load()

"""Auto-marks composers.birth_year_verified/death_year_verified TRUE
wherever there's no genuine ambiguity to resolve at all: the stored year
is exact precision (no year_upper) and matches domain.dates.
resolve_wd_claims()'s resolution of Wikidata's own P569/P570 claims, and
-- when raw text (birth_raw/death_raw) exists -- it re-parses to the
same year too. A composer with no raw text at all still qualifies as long
as Wikidata alone is unambiguous; raw agreement is only *checked* when
present, not required, so this is a weaker form of confidence than a
three-way cross-check in that case, but still real: nothing anywhere
disagrees.

This is a genuinely different path to TRUE than a hand-resolved conflict
(see birth_year_verified's own comment in schema.sql, and the Panchenko/
Bertheaume rows set by hand after actually comparing sources) -- here
nothing was ever ambiguous, so there was no judgment call to make, only
confirmation. The auto-generated note says so explicitly, so a reader
can tell the two kinds of TRUE apart at a glance.

Never touches a row already verified=TRUE -- safe to rerun, and won't
clobber a hand-written note with an auto-generated one. This is a
point-in-time snapshot, not a permanent guarantee: if Wikidata is edited
later to add a new, conflicting claim, a composer verified today won't
automatically get re-flagged. Rerun after a fresh Wikidata fetch if that
matters.

A coarse decade/century/millennium claim resolves to a 'range' via
domain.dates, which never matches an 'exact'-precision stored value by
construction (range vs. exact), so a composer whose only claims are
coarse-precision naturally falls into "wd_db_mismatch" here rather than
needing a special case -- it's just never going to match.

Usage:
    python3 verify_exact_agreeing_dates.py            # apply
    python3 verify_exact_agreeing_dates.py --dry-run   # report counts only, no writes
"""
import sys

import psycopg2
import psycopg2.extras

from domain import dates
from fetch_wikidata_relationships import extract_time_claims


def _check_one(row, prefix, entities):
    """Returns (verdict, note_or_None) for one composer's birth or death.
    verdict is one of: "already_verified", "not_exact", "no_entity",
    "no_exact_claim", "wd_internally_disagrees", "wd_db_mismatch",
    "raw_mismatch", "verified"."""
    if dates.is_pre_verified(row, prefix):
        return "already_verified", None
    precision = row[f"{prefix}_precision"]
    year = row[f"{prefix}_year"]
    year_upper = row[f"{prefix}_year_upper"]
    if precision != "exact" or year_upper is not None or year is None:
        return "not_exact", None

    qid = row["wikidata_id"]
    entity = entities.get(qid) if qid else None
    if entity is None:
        return "no_entity", None

    prop = "P569" if prefix == "birth" else "P570"
    claims = extract_time_claims(entity, prop)
    if not claims:
        return "no_exact_claim", None
    estimate = dates.resolve_wd_claims(claims)
    if estimate is None:
        return "no_exact_claim", None
    if estimate is dates.AMBIGUOUS:
        return "wd_internally_disagrees", None
    if estimate.precision != "exact" or estimate.year != year:
        return "wd_db_mismatch", None

    raw = row[f"{prefix}_raw"]
    raw_agrees = True
    if raw and raw.strip():
        raw_estimate = dates.parse_free_text(raw)
        raw_agrees = raw_estimate is not None and raw_estimate.year == year
    if not raw_agrees:
        return "raw_mismatch", None

    _winner, reason = dates.resolve_winning_claim_with_reason(claims)
    source = {
        "preferred": "Wikidata's own preferred-rank claim (a differently-ranked claim disagreed)",
        "unanimous": "every exact-precision Wikidata claim (unanimous, no rank conflict)",
        "calendar_equivalent": (
            "two Wikidata claims that looked like a disagreement but are actually the same "
            "day in the Julian and Gregorian calendars (Old Style/New Style), not a real dispute"
        ),
    }[reason]
    if raw and raw.strip():
        note = f"Auto-verified: {prefix}_raw ({raw!r}), the stored year ({year}), and {source} all agree on {year}."
    else:
        note = f"Auto-verified: no source text to cross-check, but {source} agrees on {year}."
    return "verified", note


def run(dry_run):
    conn = psycopg2.connect()
    wconn = psycopg2.connect(dbname="wikidata_entities")
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, wikidata_id,
                       birth_raw, birth_year, birth_year_upper, birth_precision, birth_year_verified,
                       death_raw, death_year, death_year_upper, death_precision, death_year_verified
                FROM composers
            """)
            rows = cur.fetchall()

        qids = sorted({r["wikidata_id"] for r in rows if r["wikidata_id"]})
        entities = {}
        with wconn.cursor() as wcur:
            for i in range(0, len(qids), 5000):
                wcur.execute("SELECT qid, entity FROM entities WHERE qid = ANY(%s)", (qids[i:i + 5000],))
                entities.update(dict(wcur.fetchall()))

        for prefix in ("birth", "death"):
            counts = {}
            to_update = []
            for row in rows:
                verdict, note = _check_one(row, prefix, entities)
                counts[verdict] = counts.get(verdict, 0) + 1
                if verdict == "verified":
                    to_update.append((row["id"], note))

            print(f"--- {prefix} ---")
            for verdict, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                print(f"  {verdict}: {n}")

            if dry_run:
                print(f"  (dry run -- would set {prefix}_year_verified=TRUE for {len(to_update)} composers)")
                continue

            with conn:
                with conn.cursor() as cur:
                    for composer_id, note in to_update:
                        cur.execute(
                            f"UPDATE composers SET {prefix}_year_verified = TRUE, "
                            f"{prefix}_year_verified_note = %s WHERE id = %s",
                            (note, composer_id),
                        )
            print(f"  set {prefix}_year_verified=TRUE for {len(to_update)} composers")
    finally:
        conn.close()
        wconn.close()


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)

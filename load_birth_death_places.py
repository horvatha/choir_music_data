"""Load exact birth/death dates and birth/death places from
wikidata_relationships.json into composers.birth_date/death_date and the
places/place_qids/place_periods tables (composers.birth_place_id/
death_place_id), resolving each composer's birth/death place to whichever
historical (name, country) window covers their birth/death year.

Reads the "place_claims" cache written by fetch_place_history.py -- every
non-deprecated P17 (country) and P1448 (official name) claim per Wikidata
place item, each with its start/end time when Wikidata records one, plus
predecessor/successor links (P1365/P1366) for places whose history is
split across multiple items (e.g. Königsberg -> Kaliningrad).

Wikidata items are NOT automatically clustered by following P1365/P1366 --
that property isn't reserved for "same city, renamed" successions; it's
used just as often for ordinary administrative-boundary reshuffling (e.g.
former Paris arrondissements renumbered in 1860, old Tokyo wards merged
into modern Tokyo, a chain of Stockholm church parishes reorganized over
centuries), and following those transitively merges unrelated places that
just happen to share an administrative lineage. There's no reliable
graph-topology rule to tell "genuine rename" apart from "boundary
reshuffle" using only P1365/P1366, so instead: every Wikidata item is its
own canonical place by default, and genuine same-place successions are
merged via MANUAL_PLACE_CLUSTERS below -- a small hand-maintained list of
QID groups, same pattern as this repo's other hand-maintained override
lists (e.g. ERA_OVERRIDES in parse_hu_wiki_composers.py) -- explicit
human judgment call per group, not a heuristic.

Modeling, in order:
  1. Group Wikidata items per MANUAL_PLACE_CLUSTERS into one canonical
     place each (everything else is a "cluster" of one).
  2. Within a cluster, order items oldest-to-newest via the predecessor
     chain. A successor's own claims always win for whatever time range
     they cover; an older item's claims are clipped to end no later than
     its successor's earliest dated claim, so e.g. Königsberg doesn't
     contribute an overlapping "still Soviet in 1946" window once
     Kaliningrad's own claims already cover 1945 onward.
  3. An item with no P1448 claims at all (most places, e.g. Moscow) gets
     one synthetic "name window" per country window, using the item's own
     Wikidata label -- guarantees every covered year has both a name and
     a country, without a separate merge step for the common case.
  4. All windows across the cluster are merged onto one timeline (every
     window's start/end becomes a breakpoint), producing one place_periods
     row per resulting sub-interval, with adjacent identical (name,
     country) intervals collapsed together.

A composer's birth_place_id/death_place_id is set to whichever
place_periods row's [start_year, end_year) covers their (already-known,
CSV- or Wikidata-sourced) birth/death year -- nearest window if the year
falls in a gap, the currently-open window if the year is unknown.

Like the date-loading half of this script, Wikidata is the only source for
this data, so it always sets the computed value straight from the cache
rather than COALESCE-preserving whatever was there before -- safe to
rerun after a fresh fetch. birth_year/death_year (used only to pick the
right window here, not overwritten with a different value) follow the
same COALESCE-only-if-missing rule as before.

Do not run this at the same time as `cli.py fetch ...`/`cli.py backfill
...` or another backfill_*.py/fetch_*.py script -- see README.md's
"Pipeline rules" for the concurrent-cache-write hazard. This script
itself makes no network calls.

Usage:
    python3 load_birth_death_places.py
"""

import psycopg2

# Hand-maintained groups of Wikidata QIDs that are genuinely the same
# real-world place despite being separate Wikidata items -- see the module
# docstring for why this isn't derived automatically from P1365/P1366.
# Add a pair/group here (each entry a set of QIDs) once confirmed by hand,
# the same way merge_composers.py pairs get confirmed before merging.
MANUAL_PLACE_CLUSTERS = [
    {"Q4120832", "Q1829"},  # Königsberg -> Kaliningrad
    {"Q239", "Q111901161", "Q9005"},  # City of Brussels + general "Brussels" concept + "Brussels metropolitan area"
]

from adapters.json_cache import load_cache
from fetch_wikidata_relationships import OUTPUT_FILE

UPSERT_COUNTRY_SQL = """
    INSERT INTO countries (name, abbr, wikidata_id)
    VALUES (%(name)s, %(abbr)s, %(wikidata_id)s)
    ON CONFLICT (wikidata_id) DO UPDATE
        SET name = EXCLUDED.name, abbr = COALESCE(countries.abbr, EXCLUDED.abbr)
    RETURNING id
"""

UPSERT_PLACE_QID_SQL = """
    INSERT INTO place_qids (place_id, wikidata_id)
    VALUES (%(place_id)s, %(wikidata_id)s)
    ON CONFLICT (wikidata_id) DO UPDATE SET place_id = EXCLUDED.place_id
    RETURNING id
"""

UPDATE_COMPOSER_SQL = """
    UPDATE composers SET
        birth_date = %(birth_date)s, birth_place_id = %(birth_place_id)s,
        birth_calendar = %(birth_calendar)s::wikidata_calendar,
        birth_year = COALESCE(birth_year, %(birth_year)s),
        birth_year_upper = COALESCE(birth_year_upper, %(birth_year_upper)s),
        birth_precision = COALESCE(birth_precision, %(birth_precision)s::date_precision),
        death_date = %(death_date)s, death_place_id = %(death_place_id)s,
        death_calendar = %(death_calendar)s::wikidata_calendar,
        death_year = COALESCE(death_year, %(death_year)s),
        death_year_upper = COALESCE(death_year_upper, %(death_year_upper)s),
        death_precision = COALESCE(death_precision, %(death_precision)s::date_precision)
    WHERE id = %(composer_id)s
"""


def _year_fallback(existing_year, date_str, year_precision):
    """Resolve birth_year/_year_upper/_precision together as one atomic
    choice, in priority order: existing DB value > day-precision Wikidata
    date (extract_dates()'s "birth"/"death") > coarser year-precision
    Wikidata claim ("birth_year_precision"/"death_year_precision", see
    fetch_wikidata_relationships.py). year_upper/precision are only ever
    non-None in the third case, so COALESCE-ing them into the DB can
    never clobber an already-exact date's correctly-NULL year_upper."""
    if existing_year is not None:
        return existing_year, None, None
    if date_str:
        return int(date_str[:4]), None, None
    if year_precision:
        return year_precision["year"], year_precision.get("year_upper"), year_precision.get("precision")
    return None, None, None


def order_chain(qids, place_claims):
    """Oldest-to-newest order of a cluster's QIDs, via each item's
    "predecessor" link (P1365) -- an item goes before its successor. Most
    clusters are a single QID (trivial order); a cycle or otherwise
    unresolvable cluster just falls back to a stable arbitrary order
    rather than looping forever."""
    remaining = set(qids)
    order = []
    while remaining:
        ready = sorted(
            q for q in remaining
            if place_claims.get(q, {}).get("predecessor") not in remaining
        )
        if not ready:
            order.extend(sorted(remaining))
            break
        order.extend(ready)
        remaining -= set(ready)
    return order


def _clip_undated_name_window(name_windows):
    """A P1448 "official name" claim with no P580/P582 time qualifiers at
    all usually represents Wikidata's *current* value for the property --
    left without a start time simply because it's still true today, not
    because it applies since the dawn of time. _window_active (below)
    turns that missing start/end into an unbounded (-inf, +inf) range, so
    without this clip it wins over every *other*, dated window for any
    point before the earliest dated claim starts too -- backwards. Real
    case that surfaced this (Q157688, Oranienbaum/Lomonosov): a dated
    P1448 claim gives "Oranienbaum" for 1780-1948, and a separate,
    undated claim gives "Lomonosov" -- the real 1948 rename, not a name
    that predates 1780 -- but naive merging put "Lomonosov" on the
    pre-1780 window instead, because nothing bounded its start.  Clips
    any undated window to start no earlier than the latest end of the
    other, dated windows in the same list, so it only fills the gap
    *after* them, matching Wikidata's usual convention (dated windows
    for historical/former names, an undated one for the current name).
    Left alone when every window in the list is already dated, or when
    every window is undated (nothing to clip against)."""
    dated_ends = [end for start, end, _v in name_windows if (start is not None or end is not None) and end is not None]
    if not dated_ends:
        return name_windows
    floor = max(dated_ends)
    return [
        (floor, None, value) if start is None and end is None else (start, end, value)
        for start, end, value in name_windows
    ]


def build_qid_windows(qid, claims, qid_labels):
    """(country_windows, name_windows) for one Wikidata item, each a list
    of (start, end, value) tuples. name_windows is None when the item has
    no P1448 claims at all -- the caller fills in a same-boundaries
    fallback from the (possibly since-clipped) country windows, using this
    item's own label."""
    dated = [
        (w["start"], w["end"], w["country_qid"])
        for w in claims.get("p17", [])
        if w["start"] is not None or w["end"] is not None
    ]
    if dated:
        country_windows = dated
    else:
        undated = claims.get("p17", [])
        chosen = next((w for w in undated if w.get("rank") == "preferred"), undated[0] if undated else None)
        country_windows = [(None, None, chosen["country_qid"])] if chosen else []

    p1448 = claims.get("p1448", [])
    if not p1448:
        return country_windows, None

    groups = {}
    for w in p1448:
        groups.setdefault((w["start"], w["end"]), []).append(w)
    name_windows = []
    for (start, end), group in groups.items():
        en_match = next((w for w in group if w["language"] == "en"), None)
        if en_match:
            best_name = en_match["name"]
        elif qid_labels.get(qid):
            # No English P1448 claim for this window -- qid_labels (Wikidata's
            # own best-label pick, already fetched) is far more reliable than
            # picking "ru" as a blanket second choice: that language-code
            # fallback used to fire for any place lacking an English name
            # claim regardless of any actual connection to Russian, e.g.
            # Liège -> "Льеж", Wrocław -> "Вроцлав", Guadalajara ->
            # "Гвадалахара" -- all wrong, none Cyrillic-script places.
            best_name = qid_labels[qid]
        else:
            best_name = (
                next((w for w in group if w["language"] == "ru"), None)
                or sorted(group, key=lambda w: w["language"])[0]
            )["name"]
        name_windows.append((start, end, best_name))
    return country_windows, _clip_undated_name_window(name_windows)


def _clip_after(windows, floor):
    """Keep only the part of each window at or after `floor`, truncating
    a window that straddles it. Used so an item earlier in a predecessor
    chain always wins for whatever time range its own claims cover --
    Wikidata's items aren't always cleanly partitioned (e.g. Kaliningrad's
    own P17 claims redundantly restate the region's pre-1946 history that
    Königsberg's own item already covers), so the later item in the chain
    only fills in time its predecessor didn't already claim."""
    if floor is None:
        return windows
    result = []
    for start, end, value in windows:
        if end is not None and end <= floor:
            continue
        result.append((floor, end, value) if start is None or start < floor else (start, end, value))
    return result


def _window_active(windows, point):
    for start, end, value in windows:
        lo = float("-inf") if start is None else start
        hi = float("inf") if end is None else end
        if lo <= point < hi:
            return value
    return None


def merge_windows_to_periods(country_windows, name_windows):
    """Union every window boundary across both lists into breakpoints,
    sample the active country/name in each resulting sub-interval, and
    collapse adjacent sub-intervals whose (name, country) ended up
    identical (e.g. Moscow: a single unbroken name across many country
    windows, collapses back to genuinely-distinct country eras only)."""
    if not country_windows and not name_windows:
        return []
    breakpoints = sorted({v for w in (country_windows + name_windows) for v in (w[0], w[1]) if v is not None})
    bounds = [None] + breakpoints + [None]
    raw = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        sample = lo if lo is not None else (hi - 1 if hi is not None else 0)
        country_qid = _window_active(country_windows, sample)
        name = _window_active(name_windows, sample)
        if country_qid is None and name is None:
            continue
        raw.append({"start": lo, "end": hi, "country_qid": country_qid, "name": name})
    merged = []
    for p in raw:
        if (merged and merged[-1]["name"] == p["name"]
                and merged[-1]["country_qid"] == p["country_qid"] and merged[-1]["end"] == p["start"]):
            merged[-1]["end"] = p["end"]
        else:
            merged.append(dict(p))
    return merged


def find_existing_place_id(cur, qids):
    cur.execute("SELECT place_id FROM place_qids WHERE wikidata_id = ANY(%s) LIMIT 1", (list(qids),))
    row = cur.fetchone()
    return row[0] if row else None


def upsert_place(cur, place_id, name, latitude, longitude):
    if place_id is None:
        cur.execute(
            "INSERT INTO places (name, latitude, longitude) VALUES (%s, %s, %s) RETURNING id",
            (name, latitude, longitude),
        )
        return cur.fetchone()[0]
    cur.execute(
        "UPDATE places SET name = %s, latitude = COALESCE(latitude, %s), longitude = COALESCE(longitude, %s) "
        "WHERE id = %s",
        (name, latitude, longitude, place_id),
    )
    return place_id


def resolve_period(periods, year):
    """periods: list of (id, start_year, end_year). Picks the window
    covering `year`; if `year` falls in a gap between two windows, the
    nearer one; if `year` is unknown, the currently-open window (or the
    most recent one, if none is open)."""
    if not periods:
        return None
    if year is not None:
        for pid, start, end in periods:
            if (start is None or start <= year) and (end is None or year < end):
                return pid

        def distance(p):
            _, start, end = p
            if start is not None and year < start:
                return start - year
            if end is not None and year >= end:
                return year - end + 1
            return 0

        return min(periods, key=distance)[0]
    open_periods = [p for p in periods if p[2] is None]
    pool = open_periods or periods
    return max(pool, key=lambda p: p[1] if p[1] is not None else -10 ** 9)[0]


def main():
    data = load_cache(OUTPUT_FILE)
    entries = data["composers"]
    qid_labels = data.get("qid_labels", {})
    place_claims = data.get("place_claims", {})
    country_info = data.get("country_info", {})

    # Only process QIDs that are themselves a composer's actual birth/death
    # place -- not every QID fetch_place_history.py happened to cache.
    seed_qids = {
        qid
        for e in entries.values()
        for qid in (
            e.get("attributes", {}).get("place_of_birth", [])
            + e.get("attributes", {}).get("place_of_death", [])
        )
    }
    fetched_seeds = seed_qids & place_claims.keys()

    parent = {}

    def find(q):
        parent.setdefault(q, q)
        while parent[q] != q:
            parent[q] = parent[parent[q]]
            q = parent[q]
        return q

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for qid in fetched_seeds:
        find(qid)
    for group in MANUAL_PLACE_CLUSTERS:
        present = [q for q in group if q in fetched_seeds]
        for a, b in zip(present, present[1:]):
            union(a, b)

    clusters = {}
    for qid in fetched_seeds:
        clusters.setdefault(find(qid), set()).add(qid)

    conn = psycopg2.connect()
    place_id_by_qid = {}
    periods_by_place = {}
    country_id_by_qid = {}
    updated = 0
    skipped_place = 0
    try:
        with conn:
            with conn.cursor() as cur:
                def country_id_for(country_qid):
                    if country_qid in country_id_by_qid:
                        return country_id_by_qid[country_qid]
                    info = country_info.get(country_qid, {})
                    cur.execute(UPSERT_COUNTRY_SQL, {
                        "name": info.get("name", country_qid), "abbr": info.get("abbr"), "wikidata_id": country_qid,
                    })
                    cid = cur.fetchone()[0]
                    country_id_by_qid[country_qid] = cid
                    return cid

                for cluster_qids in clusters.values():
                    order = order_chain(cluster_qids, place_claims)
                    raw = {q: build_qid_windows(q, place_claims.get(q, {}), qid_labels) for q in order}

                    all_country, all_name = [], []
                    floor = None
                    chain_closed = False
                    for qid in order:
                        country_w, name_w = raw[qid]
                        if chain_closed:
                            # An earlier item in this chain already has an
                            # open-ended (still current) claim -- nothing
                            # after it in the order can be a "later" era,
                            # so drop its windows rather than clip against
                            # an infinite floor (which produced a start
                            # year of +inf, rejected by Postgres as
                            # out-of-range integer).
                            country_w, name_w = [], []
                        else:
                            country_w = _clip_after(country_w, floor)
                            name_w = _clip_after(name_w, floor) if name_w is not None else None
                        if name_w is None:
                            name_w = [(s, e, qid_labels.get(qid, qid)) for s, e, _c in country_w]
                        all_country.extend(country_w)
                        all_name.extend(name_w)
                        ends = [e for _s, e, _v in country_w]
                        if any(e is None for e in ends):
                            chain_closed = True
                        elif ends:
                            floor = max(ends) if floor is None else max(floor, max(ends))

                    periods = merge_windows_to_periods(all_country, all_name)
                    if not periods:
                        continue

                    open_periods = [p for p in periods if p["end"] is None]
                    canonical_source = (
                        open_periods[-1] if open_periods
                        else max(periods, key=lambda p: p["start"] if p["start"] is not None else -10 ** 9)
                    )
                    canonical_name = canonical_source["name"] or qid_labels.get(order[-1], order[-1])

                    latitude = longitude = None
                    for qid in reversed(order):
                        coords = place_claims.get(qid, {}).get("coordinates")
                        if coords:
                            latitude, longitude = coords
                            break

                    place_id = find_existing_place_id(cur, cluster_qids)
                    place_id = upsert_place(cur, place_id, canonical_name, latitude, longitude)

                    qid_row_id = {}
                    for qid in order:
                        cur.execute(UPSERT_PLACE_QID_SQL, {"place_id": place_id, "wikidata_id": qid})
                        qid_row_id[qid] = cur.fetchone()[0]
                    for qid in order:
                        pred = place_claims.get(qid, {}).get("predecessor")
                        if pred in qid_row_id:
                            cur.execute(
                                "UPDATE place_qids SET predecessor_place_qid_id = %s WHERE id = %s",
                                (qid_row_id[pred], qid_row_id[qid]),
                            )

                    cur.execute("DELETE FROM place_periods WHERE place_id = %s", (place_id,))
                    period_rows = []
                    for p in periods:
                        country = country_info.get(p["country_qid"], {}) if p["country_qid"] else {}
                        cid = country_id_for(p["country_qid"]) if p["country_qid"] else None
                        cur.execute(
                            "INSERT INTO place_periods (place_id, name, default_language, country_id, country_code, start_year, end_year) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                            (place_id, p["name"] or canonical_name, country.get("language"),
                             cid, country.get("abbr"), p["start"], p["end"]),
                        )
                        period_rows.append((cur.fetchone()[0], p["start"], p["end"]))
                    periods_by_place[place_id] = period_rows

                    for qid in cluster_qids:
                        place_id_by_qid[qid] = place_id

                print(f"Resolved {len(clusters)} canonical places from {len(fetched_seeds)} composer-referenced Wikidata items "
                      f"({len(place_claims) - len(fetched_seeds)} other cached items ignored).")

                cur.execute("SELECT id, birth_year, death_year FROM composers")
                composer_years = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

                def resolve(qids, year):
                    nonlocal skipped_place
                    if not qids:
                        return None
                    place_id = place_id_by_qid.get(qids[0])
                    if place_id is None:
                        skipped_place += 1
                        return None
                    return resolve_period(periods_by_place.get(place_id, []), year)

                for composer_id, entry in entries.items():
                    if not entry.get("applied_to_db"):
                        continue
                    dates = entry.get("dates", {})
                    attributes = entry.get("attributes", {})
                    if not dates and "place_of_birth" not in attributes and "place_of_death" not in attributes:
                        continue

                    cid = int(composer_id)
                    existing_birth_year, existing_death_year = composer_years.get(cid, (None, None))
                    birth_year, birth_year_upper, birth_precision = _year_fallback(
                        existing_birth_year, dates.get("birth"), dates.get("birth_year_precision"))
                    death_year, death_year_upper, death_precision = _year_fallback(
                        existing_death_year, dates.get("death"), dates.get("death_year_precision"))

                    cur.execute(UPDATE_COMPOSER_SQL, {
                        "composer_id": cid,
                        "birth_date": dates.get("birth"),
                        "birth_calendar": dates.get("birth_calendar"),
                        "birth_place_id": resolve(attributes.get("place_of_birth", []), birth_year),
                        "birth_year": birth_year, "birth_year_upper": birth_year_upper, "birth_precision": birth_precision,
                        "death_date": dates.get("death"),
                        "death_calendar": dates.get("death_calendar"),
                        "death_place_id": resolve(attributes.get("place_of_death", []), death_year),
                        "death_year": death_year, "death_year_upper": death_year_upper, "death_precision": death_precision,
                    })
                    updated += 1
    finally:
        conn.close()
    print(f"Updated {updated} composers with dates/places "
          f"({len(place_id_by_qid)} place QIDs across {len(periods_by_place)} canonical places, "
          f"{len(country_id_by_qid)} distinct countries, {skipped_place} places skipped -- "
          f"QID not in place_claims cache, rerun fetch_place_history.py first).")
    print("You should also run load_place_period_names.py now -- this just "
          "regenerated place_periods with fresh ids, which wiped place_period_names.")


if __name__ == "__main__":
    main()

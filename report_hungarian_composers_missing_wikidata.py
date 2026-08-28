"""Report Hungarian composers with no Wikidata link at all
(composers.wikidata_id IS NULL) -- these are the composers no
fetch/backfill script in this repo can enrich (dates, places, images,
relations, ...) since everything downstream keys off the QID.

For each one, flags two independent leads for finding/confirming a QID
by hand:

- LFZE: has an "LFZE - Nagy elődök" other_webpages entry (source =
  'lfze_nagy_elodok', e.g. https://lfze.hu/nagy-elodok/... via
  load_lfze_nagy_elodok.py) -- a named-faculty biography page, a strong
  signal this is a real, notable composer worth chasing down.
- WP: has at least one composer_wikilinks row (any language) -- a
  Wikipedia article's own sidebar/Wikidata-link almost always gives the
  QID directly, so this is the easiest case to resolve.

"Hungarian" is composer_nationalities' structured 'Hungarian' tag OR
the flat composers.nationality text containing "Hungarian" (belt and
braces -- see CLAUDE.md on the two normally being kept in sync, but this
report shouldn't miss a candidate over a sync gap).

Usage:
    python3 report_hungarian_composers_missing_wikidata.py
"""
import psycopg2
import psycopg2.extras

OUTPUT_FILE = "reports/hungarian_composers_missing_wikidata.md"

CANDIDATES_SQL = """
    SELECT
        c.id,
        c.name,
        EXISTS (
            SELECT 1 FROM other_webpages ow
            WHERE ow.composer_id = c.id AND ow.source = 'lfze_nagy_elodok'
        ) AS has_lfze,
        EXISTS (
            SELECT 1 FROM composer_wikilinks cw WHERE cw.composer_id = c.id
        ) AS has_wp
    FROM composers c
    WHERE c.wikidata_id IS NULL
      AND (
        EXISTS (
            SELECT 1 FROM composer_nationalities cn
            JOIN nationalities n ON n.id = cn.nationality_id
            WHERE cn.composer_id = c.id AND n.name = 'Hungarian'
        )
        OR c.nationality ILIKE '%hungarian%'
      )
    ORDER BY has_wp DESC, has_lfze DESC, c.name
"""


def _mark(value: bool) -> str:
    return "v" if value else "x"


def main():
    conn = psycopg2.connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(CANDIDATES_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    lfze_count = sum(1 for r in rows if r["has_lfze"])
    wp_count = sum(1 for r in rows if r["has_wp"])

    lines = [
        "# Hungarian composers with no Wikidata link",
        "",
        f"{len(rows)} composers tagged Hungarian have no wikidata_id at all -- "
        "none of this repo's Wikidata-driven fetch/backfill scripts can enrich them "
        "(dates, places, images, relations) until one is found and added by hand.",
        "",
        f"{wp_count} have a Wikipedia article already (WP) -- easiest case, the article's "
        f"own sidebar usually links straight to its Wikidata item. {lfze_count} have an "
        "LFZE \"Nagy elődök\" faculty biography page (LFZE) -- a strong signal they're a "
        "real, notable composer worth chasing down even without a Wikipedia article.",
        "",
        "\"Q...\" is left blank for filling in by hand once a QID is found/confirmed.",
        "",
        "| name | Q... | id | LFZE | WP |",
        "|---|---|---:|:-:|:-:|",
    ]
    for r in rows:
        lines.append(f"| {r['name']} | | {r['id']} | {_mark(r['has_lfze'])} | {_mark(r['has_wp'])} |")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"{len(rows)} candidates ({wp_count} with WP, {lfze_count} with LFZE). Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

"""Load the composers already matched to this repo's DB (see
match_swedish_heritage_composers.py's composers_swedish_heritage_matched.csv,
in_the_db=true rows) into other_webpages, linking each to its composer
row -- same purpose and shape as load_lfze_nagy_elodok.py, but matching
primarily by wikidata_id (already resolved by the matching script) since
that's unambiguous, unlike name-token matching. Falls back to
adapters/name_matching's normalize_tokens() (shared with
load_lfze_nagy_elodok.py) only for the rare row where the matched DB
composer has no wikidata_id of its own yet.

No new composer rows are created here, and no dates/bio/works content
is loaded into the DB from Swedish Heritage yet -- this is just the
article link, the same first step LFZE went through before any of its
other data got used.

fetched_at is the saved JSON file's mtime (when the page was actually
crawled), not the time this loader happens to run.

Safe to rerun: other_webpages is upserted on its (composer_id, source)
primary key.

Usage:
    python3 load_swedish_heritage.py
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from adapters.name_matching import normalize_tokens

MATCHED_CSV = Path(__file__).resolve().parent / "data" / "Swedish_Heritage" / "composers_swedish_heritage_matched.csv"
JSON_DIR = Path(__file__).resolve().parent / "data" / "Swedish_Heritage"
SOURCE = "swedish_heritage"

FETCH_ALL_COMPOSERS_SQL = "SELECT id, name, wikidata_id FROM composers"

INSERT_OTHER_WEBPAGE_SQL = """
    INSERT INTO other_webpages (composer_id, source, url, language, title, author, fetched_at)
    VALUES (%(composer_id)s, %(source)s, %(url)s, %(language)s, %(title)s, %(author)s, %(fetched_at)s)
    ON CONFLICT (composer_id, source) DO UPDATE SET
        url = EXCLUDED.url, language = EXCLUDED.language, title = EXCLUDED.title,
        author = EXCLUDED.author, fetched_at = EXCLUDED.fetched_at
"""


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def main():
    with open(MATCHED_CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["in_the_db"] == "true"]

    conn = psycopg2.connect()
    conn.autocommit = True
    linked = []
    skipped = []
    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_ALL_COMPOSERS_SQL)
            all_composers = cur.fetchall()
            by_wikidata_id = {wid: cid for cid, _name, wid in all_composers if wid}
            by_tokens: dict[frozenset, list] = {}
            for cid, name, _wid in all_composers:
                if name:
                    by_tokens.setdefault(normalize_tokens(name), []).append((cid, name))

            for row in rows:
                composer_id = by_wikidata_id.get(row["wikidata_id"]) if row["wikidata_id"] else None
                if composer_id is None:
                    candidates = by_tokens.get(normalize_tokens(row["name"]), [])
                    if len(candidates) != 1:
                        skipped.append((row["name"], "no wikidata_id and name match isn't unique"))
                        continue
                    composer_id = candidates[0][0]

                slug = slug_from_url(row["url"])
                json_path = JSON_DIR / f"{slug}.json"
                if not json_path.exists():
                    skipped.append((row["name"], f"no JSON file for slug {slug!r}"))
                    continue
                data = json.loads(json_path.read_text(encoding="utf-8"))
                fetched_at = datetime.fromtimestamp(json_path.stat().st_mtime, tz=timezone.utc)

                cur.execute(INSERT_OTHER_WEBPAGE_SQL, {
                    "composer_id": composer_id, "source": SOURCE, "url": data["composer_url"],
                    "language": "sv", "title": data["name"], "author": None, "fetched_at": fetched_at,
                })
                linked.append((row["name"], composer_id))
    finally:
        conn.close()

    print(f"Linked {len(linked)} composers to other_webpages (source={SOURCE!r}):")
    for name, cid in linked:
        print(f"  {name} -> composer_id={cid}")

    if skipped:
        print(f"\nNot loaded ({len(skipped)}):")
        for name, reason in skipped:
            print(f"  {name}: {reason}")


if __name__ == "__main__":
    main()

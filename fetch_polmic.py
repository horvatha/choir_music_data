"""Crawl POLMIC's Polish Music Information Centre online encyclopedia
(polmic.pl/en/encyclopedia/subject-entries/), saving one structured JSON
file per composer into data/POLMIC/ -- same overall shape as
fetch_swedish_heritage.py, reusing adapters/page_fetch.py and
adapters/date_parsing.py rather than duplicating them a second time.

The encyclopedia mixes composers with musicologists/performers/
institutions (2,600+ entries total) -- each entry's own "Occupation"
field (a short list like "composer, performer") is the only reliable
signal, so every entry has to be fetched and checked, same as LFZE's
"zeneszerz" stem classifier, just simpler since it's already English.

The index isn't a single page like Swedish Heritage's -- it's letter-
based like LFZE, but with two independent layers of splitting: some
busy letters get a second (or third) *separate* index page ("s-1",
"z-1", "z-2" -- literally more surnames starting with the same letter,
not a different grouping), and within any one of those, results are
further paginated via Joomla's "?start=N" (48 per page) if there are
more than 48. Both layers are walked here.

English-language entries only (the "-en" URL suffix) -- POLMIC's own
Polish-language encyclopedia is a separate, larger set this doesn't
attempt to also crawl.

Usage:
    python3 fetch_polmic.py
    python3 fetch_polmic.py --csv
    python3 fetch_polmic.py --limit 20 --csv  # smoke test
"""
import csv
import json
import re
import time
import urllib.error
from pathlib import Path

import click

from adapters.date_parsing import (
    parse_abbreviated_birth_death,
    parse_born_died_noplace,
    parse_born_died_sentence,
)
from adapters.page_fetch import fetch as fetch_bytes
from adapters.page_fetch import strip_tags

USER_AGENT = "choir_music_data-polmic-fetch/1.0 (personal research script)"
BASE_URL = "https://polmic.pl"
LETTER_SLUGS = [
    "a", "b", "c", "c-1", "d", "e", "f", "g", "h", "i", "j", "k", "l", "l-1",
    "m", "n", "o", "p", "q", "r", "s", "s-1", "t", "u", "v", "w", "x", "y",
    "z", "z-1", "z-2",
]
PAGE_SIZE = 48
OUT_DIR = Path(__file__).resolve().parent / "data" / "POLMIC"
DEFAULT_CSV_PATH = OUT_DIR / "composers_polmic.csv"

ENTRY_LINK_RE = re.compile(r'href="(/en/encyclopedia/subject-entries/[a-z0-9-]+/[a-z0-9-]+-en)"')
NAME_RE = re.compile(r'<h1 class="uk-heading-line uk-text-center">\s*<span>\s*(.*?)\s*</span>\s*</h1>', re.DOTALL)
OCCUPATION_RE = re.compile(r'<ul class="uk-list">.*?<div class="el-content uk-panel">(.*?)</div>', re.DOTALL)
DESCRIPTION_RE = re.compile(r'</ul><div class="uk-panel uk-margin">(.*?)</div>\s*<h2', re.DOTALL)
# The works list is sometimes <ul><li>...</li></ul> (Panufnik), sometimes
# a bare run of <p>...</p> (Araszkiewicz Franciszek) -- capture the whole
# section, then try both item shapes against it.
WORKS_RE = re.compile(r'<h2 id="kompozycje">.*?</h2><div class="uk-panel uk-margin">(.*?)</div>', re.DOTALL)
WORK_ITEM_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)
WORK_ITEM_PARA_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)
WORK_YEAR_RE = re.compile(r"\((\d{4}(?:-\d{2,4})?)\)\s*$")
PUBLICATIONS_RE = re.compile(r'<h2 id="publikacje">.*?</h2><div class="uk-panel uk-margin">(.*?)</div>', re.DOTALL)
BIBLIOGRAPHY_RE = re.compile(r'<h2 id="literatura">.*?</h2><div class="uk-panel uk-margin">(.*?)</div>', re.DOTALL)


def collect_entry_links(limit: int | None = None) -> list[dict]:
    """Walks every letter-index page (and each one's ?start=N pagination)
    collecting entry links, deduplicated by URL. Stops early once `limit`
    unique links are found, if given (for smoke testing -- still visits
    whole index pages, just stops requesting more once enough links are
    in hand)."""
    entries = []
    seen = set()
    for letter_slug in LETTER_SLUGS:
        start = 0
        while True:
            url = f"{BASE_URL}/en/encyclopedia/subject-entries/{letter_slug}"
            if start:
                url += f"?start={start}"
            html = fetch_bytes(url, USER_AGENT).decode("utf-8")
            links = ENTRY_LINK_RE.findall(html)
            new_links = [l for l in links if l not in seen]
            for path in new_links:
                seen.add(path)
                slug = path.rsplit("/", 1)[-1]
                entries.append({"slug": slug, "url": f"{BASE_URL}{path}"})
            time.sleep(0.3)
            if len(links) < PAGE_SIZE or not new_links:
                break
            start += PAGE_SIZE
            if limit and len(entries) >= limit:
                return entries[:limit]
        if limit and len(entries) >= limit:
            return entries[:limit]
    return entries


def _extract(regex, html, group=1):
    m = regex.search(html)
    return strip_tags(m.group(group)) if m else None


def _parse_works(html: str) -> list[dict]:
    m = WORKS_RE.search(html)
    if not m:
        return []
    items = WORK_ITEM_RE.findall(m.group(1)) or WORK_ITEM_PARA_RE.findall(m.group(1))
    works = []
    for item_html in items:
        title = strip_tags(item_html)
        if not title:
            continue
        year_m = WORK_YEAR_RE.search(title)
        works.append({"title": title, "year": year_m.group(1) if year_m else None})
    return works


def parse_entry_page(html: str, slug: str, url: str) -> dict:
    name = _extract(NAME_RE, html)
    occupation = _extract(OCCUPATION_RE, html)
    description = _extract(DESCRIPTION_RE, html)

    birth = {"place": None, "date": None, "raw": None}
    death = {"place": None, "date": None, "raw": None}
    if description:
        # Tried in this order: "b. DATE in PLACE" is the majority style
        # here (e.g. Andrzej Panufnik), but a real minority write the
        # full word instead (Wojciech Kilar: "Born in Lviv on 17 July
        # 1932, died in Katowice on 29 December 2013") -- only fall to
        # the next tier for whichever half (birth/death independently)
        # the previous tier didn't find, same "half now, half later"
        # shape fetch_swedish_heritage.py's tiers use.
        birth, death = parse_abbreviated_birth_death(description)
        if not birth["date"] or not death["date"]:
            en_birth, en_death = parse_born_died_sentence(description, birth_place=birth["place"])
            if not birth["date"]:
                birth = en_birth
            if not death["date"]:
                death = en_death
        if not birth["date"] or not death["date"]:
            noplace_birth, noplace_death = parse_born_died_noplace(description)
            if not birth["date"]:
                birth = noplace_birth
            if not death["date"]:
                death = noplace_death

    return {
        "composer_url": url,
        "title": name,
        "name": name,
        "occupation": occupation,
        "is_composer": bool(occupation and "composer" in occupation.lower()),
        "description": description,
        "birth": birth,
        "death": death,
        "works": _parse_works(html),
        "publications": _extract(PUBLICATIONS_RE, html),
        "bibliography": _extract(BIBLIOGRAPHY_RE, html),
        "slug": slug,
    }


def _csv_row(data: dict) -> dict:
    return {
        "name": data["name"] or "",
        "is_composer": "true" if data["is_composer"] else "false",
        "birth_date": data["birth"]["date"] or "",
        "birth_place": data["birth"]["place"] or "",
        "death_date": data["death"]["date"] or "",
        "death_place": data["death"]["place"] or "",
        "url": data["composer_url"],
    }


CSV_FIELDS = ["name", "is_composer", "birth_date", "birth_place", "death_date", "death_place", "url"]


def _build_csv_from_saved_json():
    json_files = sorted(OUT_DIR.glob("*.json"))
    if not json_files:
        raise click.ClickException(f"No JSON files found in {OUT_DIR} -- run a fetch first (without --csv).")
    rows = [_csv_row(json.loads(p.read_text(encoding="utf-8"))) for p in json_files]
    with open(DEFAULT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows (from {len(json_files)} saved JSON files) to {DEFAULT_CSV_PATH}")


@click.command()
@click.option("--csv", "csv_only", is_flag=True, help=f"Don't fetch -- just (re)build {DEFAULT_CSV_PATH} from already-saved JSON files.")
@click.option("--limit", type=int, default=None, help="Only fetch the first N entries (for testing).")
def main(csv_only: bool, limit: int | None):
    if csv_only:
        _build_csv_from_saved_json()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Collecting entry links from the letter index (including pagination)...")
    entries = collect_entry_links(limit=limit)
    print(f"{len(entries)} entries found")

    composer_count = 0
    failed = []
    for i, entry in enumerate(entries, 1):
        json_path = OUT_DIR / f"{entry['slug']}.json"
        if json_path.exists():
            continue
        try:
            html = fetch_bytes(entry["url"], USER_AGENT).decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  {entry['slug']}: fetch failed ({e}), skipping")
            failed.append(entry["slug"])
            continue

        data = parse_entry_page(html, entry["slug"], entry["url"])
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if data["is_composer"]:
            composer_count += 1

        if i % 50 == 0:
            print(f"  ...{i}/{len(entries)}", flush=True)
        time.sleep(0.3)

    print(f"JSON files saved in {OUT_DIR}")
    print(f"Composers (occupation contains 'composer'): {composer_count}")
    if failed:
        print(f"Failed to fetch ({len(failed)}): {', '.join(failed)}")


if __name__ == "__main__":
    main()

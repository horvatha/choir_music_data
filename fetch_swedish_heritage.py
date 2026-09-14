"""Crawl the Swedish Musical Heritage composer directory
(https://www.swedishmusicalheritage.com/composers/), saving one
structured JSON file per composer -- biography, publications/
bibliography/sources sections, external links, and the full catalogued
works list (grouped by category, each work linking to its own page) --
into data/Swedish_Heritage/.

The composer index is a single page (no pagination -- every letter's
entries are already in the HTML, just toggled by JS), so this only ever
makes one index request plus one request per composer.

Not every composer page has the same sections: living composers (e.g.
Savannah Agger) get a boilerplate "see Svensk Musik and the composer's
own website" line instead of a birth/death summary, and no works list at
all -- every field here is therefore optional and simply omitted/null
when the page doesn't have it, never guessed.

Usage:
    python3 fetch_swedish_heritage.py
    python3 fetch_swedish_heritage.py --csv
    python3 fetch_swedish_heritage.py --limit 20 --csv  # smoke test
"""
import csv
import json
import re
import time
import urllib.error
from pathlib import Path

import click

from adapters.date_parsing import DAY_PRECISION_DATE, parse_abbreviated_birth_death
from adapters.page_fetch import fetch as fetch_bytes
from adapters.page_fetch import strip_tags

USER_AGENT = "choir_music_data-swedish-heritage-fetch/1.0 (personal research script)"
BASE_URL = "https://www.swedishmusicalheritage.com"
INDEX_URL = f"{BASE_URL}/composers/"
OUT_DIR = Path(__file__).resolve().parent / "data" / "Swedish_Heritage"
DEFAULT_CSV_PATH = OUT_DIR / "composers_swedish_heritage.csv"

COMPOSER_LINK_RE = re.compile(r'<a href="(/composers/[a-z0-9-]+/)" title="([^"]*)"')

NAME_YEARS_RE = re.compile(
    r'<h2 class="mb-4 font-serif[^"]*">(.*?)<span class="normal-weight">\(([^)]*)\)</span>',
    re.DOTALL,
)
SUMMARY_RE = re.compile(r'<strong style="letter-spacing: 1px;">(.*?)</strong>', re.DOTALL)

# The bio summary sentence is free text, and not every composer page is
# even in English -- roughly half (e.g. Edvin Kallstenius, Johann
# Gottlieb Adam) only got a Swedish entry, with day-precision dates just
# as often as the English ones ("fodd i Filipstad 29 augusti 1881, dod i
# Stockholm 22 november 1967"), so it's worth matching those too rather
# than leaving that whole language behind. Still, this is free prose
# written independently for ~1000 people over years, not a template --
# some sentence shapes are rare/oddly-built enough (e.g. Peterson-Berger:
# "...until his death in Ostersund on 3 December 1942 he lived...", the
# date embedded mid-clause) that they're not worth chasing; those simply
# stay unparsed, with the raw summary always kept regardless so nothing
# is actually lost, just not structured. Confirmed shapes handled:
#   English, place before date:
#     "born in PLACE on DATE, deceased at PLACE2 on DATE2."      (Alfvén)
#     "born in PLACE on DATE where he also died on DATE2."       (Acerbi, same place)
#     "born in PLACE on DATE and died in PLACE2 on DATE2."       (Almén, Albrici)
#     "...was born in PLACE on DATE and died there on DATE2."    (Rangström, same place)
#   English, date before place:
#     "born on DATE in PLACE and died on DATE2 in PLACE2."       (Agrell)
#     "born DATE in PLACE, was one of... died on DATE2 in PLACE2." (Stenhammar -- no "on" before birth date)
#   Swedish:
#     "fodd i PLACE DATE, dod i PLACE2 DATE2."                   (Kallstenius)
#     "foddes den DATE (oklart var). Avled i PLACE2 den DATE2."  (Adam -- birth place unknown)
_DATE = DAY_PRECISION_DATE  # shared with adapters/date_parsing.py and fetch_polmic.py
_SV_DATE = r"\d{1,2}\s+[a-zA-ZåäöÅÄÖ]+\s+\d{4}"
# Place-capturing groups are restricted to [^.]+? (never crossing a full
# stop) rather than a bare .+? -- the regex runs against the *whole*
# multi-sentence summary paragraph, not just the birth/death sentence in
# isolation, so an unrestricted .+? happily skips right over the comma/
# period after the real place and keeps consuming text until it finds a
# much later "and" or "on DATE" match elsewhere in the bio (found via
# Stenhammar: birth "place" came back as half his biography).
# "on" before the date is itself optional and inconsistently used across
# the site's freeform prose (found via Wilhelm Uddén: "born in Stockholm
# 4 August 1799 and died there 3 May 1868", no "on" anywhere) -- applied
# to every place/date pattern below, not just the two spots (Stenhammar,
# Du Puy) where it was first noticed.
# The place capture must not cross a "died" clause -- found via Conrad
# Friedrich Hurlebusch: "born in Brunswick, Northern Germany in 1691
# (baptised 30 December) and died in Amsterdam 17 December 1765." His
# birth is genuinely year-only (no day/month attached to "1691"; "30
# December" is a baptism date, a different event, with no year of its
# own nearby), so unguarded this pattern ran straight past "and died in
# Amsterdam" and matched the DEATH date/place as if they were birth's.
BORN_PLACE_DATE_RE = re.compile(rf"born (?:in|at) ((?:(?!died|\.).)+?)\s+(?:on\s+)?({_DATE})")
# Two-tier fallback, tried in this order: PLACE can itself contain a
# comma (e.g. "Löth parish, Östergötland"), so prefer stopping at " and"
# (the Agrell shape: "...in PLACE and died...") and only fall back to
# stopping at the first comma/period (the Stenhammar shape: "...in
# PLACE, was one of...", no "and died" continuation) when no " and"
# is found -- a comma-stop alone would wrongly truncate a comma-
# containing place name in the first shape.
BORN_DATE_PLACE_AND_RE = re.compile(rf"born (?:on )?({_DATE}) in ([^.]+?)\s+and\s+died\b")
BORN_DATE_PLACE_PUNCT_RE = re.compile(rf"born (?:on )?({_DATE}) in ([^.,]+)[.,]")
DIED_SAME_PLACE_RE = re.compile(rf"died there (?:on )?({_DATE})|where (?:he|she|they) (?:also )?died (?:on )?({_DATE})")
DIED_PLACE_DATE_RE = re.compile(rf"(?:deceased|died) (?:at|in) ([^.]+?)\s+(?:on\s+)?({_DATE})")
DIED_DATE_PLACE_RE = re.compile(rf"died (?:on )?({_DATE}) in ([^.]+?)\.")
# "b."/"d." abbreviated form (found via Bror Beckman: "b. 10 February
# 1866 in Kristinehamn, d. 22 July 1929 in Ljungskile.", "in PLACE" or
# ", PLACE" both occur -- Erik Gustaf Geijer's entry uses the comma
# form), tried after the full "born"/"died" patterns since it's a less
# common style -- shared adapters/date_parsing.parse_abbreviated_birth_
# death(), since this exact shape recurred verbatim on polmic.pl too.
# Last-resort, no-place fallbacks -- some entries never name a place at
# all for one or both events (found via Bengt Wilhelm Hallberg: "was born
# on 13 May 1824 and died 4 May 1883", no place anywhere in the
# sentence). Tried only after every place-aware pattern above has failed.
BORN_DATE_NOPLACE_RE = re.compile(rf"born (?:on )?({_DATE})\b")
DIED_DATE_NOPLACE_RE = re.compile(rf"died (?:on )?({_DATE})\b")
# Swedish patterns, case-insensitive throughout -- "Född"/"Avled" routinely
# start a sentence (found via Sigrid Johansson: "Född 19 oktober 1874 i
# Uppsala, död därstädes 1 december 1964", missed entirely by the
# lowercase-only patterns below plus two more gaps: "Född DATE i PLACE"
# is date-before-place, the Swedish mirror of BORN_DATE_PLACE_* above,
# never handled; and "därstädes" ("there") is Swedish's same-place-death
# shape, the mirror of DIED_SAME_PLACE_RE, likewise never handled.
SV_BORN_PLACE_DATE_RE = re.compile(rf"född(?:es)? i ((?:(?!död|avled|\.).)+?)(?: den)? ({_SV_DATE})", re.IGNORECASE)
SV_BORN_DATE_PLACE_RE = re.compile(rf"född(?:es)? ({_SV_DATE}) i ([^.,]+)", re.IGNORECASE)
# "den" before the date is itself optional here too (found via Gustaf
# III: "född 13 januari 1746 (g.s.), död 29 mars 1792", no "den"
# anywhere and no place at all for either event).
SV_BORN_DATE_ONLY_RE = re.compile(rf"född(?:es)? (?:den )?({_SV_DATE})", re.IGNORECASE)
SV_DIED_RE = re.compile(rf"(?:död|avled(?:es)?|avliden) i ([^.]+?)(?: den)? ({_SV_DATE})", re.IGNORECASE)
SV_DIED_SAME_PLACE_RE = re.compile(rf"(?:död|avled(?:es)?|avliden) (?:därstädes|där) (?:den )?({_SV_DATE})", re.IGNORECASE)
# Swedish date-before-place death, the mirror of SV_BORN_DATE_PLACE_RE --
# never added earlier even though the birth-side mirror was (found via
# Erik Gabriel von Rosén / Carl Adam Norman: "Avled den 24 mars 1812 i
# Hovförsamlingen, Stockholm."). Place-comma-truncation is an accepted
# minor imperfection here (stops at "Hovförsamlingen", not the full
# "Hovförsamlingen, Stockholm") -- the date is the part that matters.
SV_DIED_DATE_PLACE_RE = re.compile(rf"(?:död|avled(?:es)?|avliden) (?:den )?({_SV_DATE}) i ([^.,]+)", re.IGNORECASE)
# Swedish no-place fallback, the mirror of DIED_DATE_NOPLACE_RE -- found
# via Ludvig Olofsson: "född 26 februari 1877, död 19 juli 1930."
SV_DIED_DATE_NOPLACE_RE = re.compile(rf"(?:död|avled(?:es)?|avliden) (?:den )?({_SV_DATE})\b", re.IGNORECASE)


def _parse_birth(summary: str) -> dict:
    m = BORN_PLACE_DATE_RE.search(summary)
    if m:
        return {"place": m.group(1).strip(), "date": m.group(2).strip(), "raw": m.group(0)}
    m = BORN_DATE_PLACE_AND_RE.search(summary)
    if m:
        return {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}
    m = BORN_DATE_PLACE_PUNCT_RE.search(summary)
    if m:
        return {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}
    m = SV_BORN_PLACE_DATE_RE.search(summary)
    if m:
        return {"place": m.group(1).strip(), "date": m.group(2).strip(), "raw": m.group(0)}
    m = SV_BORN_DATE_PLACE_RE.search(summary)
    if m:
        return {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}
    abbrev_birth, _abbrev_death = parse_abbreviated_birth_death(summary)
    if abbrev_birth["date"]:
        return abbrev_birth
    m = SV_BORN_DATE_ONLY_RE.search(summary)
    if m:
        return {"place": None, "date": m.group(1).strip(), "raw": m.group(0)}
    m = BORN_DATE_NOPLACE_RE.search(summary)
    if m:
        return {"place": None, "date": m.group(1).strip(), "raw": m.group(0)}
    return {"place": None, "date": None, "raw": None}


def _parse_death(summary: str, birth_place: str | None) -> dict:
    m = DIED_SAME_PLACE_RE.search(summary)
    if m:
        return {"place": birth_place, "date": (m.group(1) or m.group(2)).strip(), "raw": m.group(0)}
    m = DIED_PLACE_DATE_RE.search(summary)
    if m:
        return {"place": m.group(1).strip(), "date": m.group(2).strip(), "raw": m.group(0)}
    m = DIED_DATE_PLACE_RE.search(summary)
    if m:
        return {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}
    m = SV_DIED_SAME_PLACE_RE.search(summary)
    if m:
        return {"place": birth_place, "date": m.group(1).strip(), "raw": m.group(0)}
    m = SV_DIED_RE.search(summary)
    if m:
        return {"place": m.group(1).strip(), "date": m.group(2).strip(), "raw": m.group(0)}
    m = SV_DIED_DATE_PLACE_RE.search(summary)
    if m:
        return {"place": m.group(2).strip(), "date": m.group(1).strip(), "raw": m.group(0)}
    _abbrev_birth, abbrev_death = parse_abbreviated_birth_death(summary)
    if abbrev_death["date"]:
        return abbrev_death
    m = DIED_DATE_NOPLACE_RE.search(summary)
    if m:
        return {"place": None, "date": m.group(1).strip(), "raw": m.group(0)}
    m = SV_DIED_DATE_NOPLACE_RE.search(summary)
    if m:
        return {"place": None, "date": m.group(1).strip(), "raw": m.group(0)}
    return {"place": None, "date": None, "raw": None}

FIELD_RE = {
    "biography": re.compile(r'<div class="format-field readmore-full-bio readmore-full-field">(.*?)</div>', re.DOTALL),
    "publications": re.compile(r'<div class="format-field readmore-full-publications readmore-full-field">(.*?)</div>', re.DOTALL),
    "bibliography": re.compile(r'<div class="format-field readmore-full-publicity readmore-full-field">(.*?)</div>', re.DOTALL),
    "sources": re.compile(r'<div class="format-field readmore-full-sources readmore-full-field">(.*?)</div>', re.DOTALL),
}
LINKS_FIELD_RE = re.compile(r'<div class="format-field readmore-full-links readmore-full-field">(.*?)</div>', re.DOTALL)
LINK_RE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>')

WORKS_SUMMARY_RE = re.compile(r'<h3 class="subheading">Summary list of works</h3>\s*<p>(.*?)</p>', re.DOTALL)
WORKS_LI_RE = re.compile(r'<li class="(list-cat|work)">(.*?)</li>', re.DOTALL)
WORK_LINK_RE = re.compile(r'<a href="(/composers/[^"]+)"[^>]*>(.*?)</a>')
OPUS_RE = re.compile(r"\bopus\s+([\w./-]+)", re.IGNORECASE)
RUDEN_RE = re.compile(r"Rud[ée]n no\.\s*([\w./-]+)", re.IGNORECASE)


def collect_composer_links() -> list[dict]:
    """Every composer's (slug, url, index_title) from the single index
    page -- index_title is the "Surname, Firstname (1872-1960)" form
    from the link's title attribute, kept only for cross-checking/
    reporting, not as the primary name source (the detail page's own
    <h2> is)."""
    html = fetch_bytes(INDEX_URL, USER_AGENT).decode("utf-8")
    composers = []
    seen = set()
    for path, title in COMPOSER_LINK_RE.findall(html):
        slug = path.strip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)
        composers.append({"slug": slug, "url": f"{BASE_URL}{path}", "index_title": title})
    return composers


_SUBHEADING_RE = re.compile(r'<h3 class="subheading">.*?</h3>', re.DOTALL)


def _parse_field(html: str, field: str) -> str | None:
    m = FIELD_RE[field].search(html)
    if not m:
        return None
    # Drop the field's own repeated subheading (e.g. "Sources") from the
    # body text -- redundant with the JSON key it's stored under.
    body = _SUBHEADING_RE.sub("", m.group(1))
    text = strip_tags(body)
    return text or None


def _parse_links(html: str) -> list[dict]:
    m = LINKS_FIELD_RE.search(html)
    if not m:
        return []
    return [{"title": strip_tags(text), "url": url} for url, text in LINK_RE.findall(m.group(1))]


def _parse_works(html: str) -> list[dict]:
    works = []
    category = None
    for kind, content in WORKS_LI_RE.findall(html):
        if kind == "list-cat":
            category = strip_tags(content)
            continue
        link_m = WORK_LINK_RE.search(content)
        if not link_m:
            continue
        rel_url, title_html = link_m.groups()
        title = strip_tags(title_html)
        opus_m = OPUS_RE.search(title)
        ruden_m = RUDEN_RE.search(title)
        works.append({
            "category": category,
            "title": title,
            "opus": opus_m.group(1) if opus_m else None,
            "ruden_no": ruden_m.group(1) if ruden_m else None,
            "url": f"{BASE_URL}{rel_url}",
            "has_published_edition": "smh-crown" in content,
        })
    return works


def parse_composer_page(html: str, slug: str, url: str) -> dict:
    name_m = NAME_YEARS_RE.search(html)
    name = strip_tags(name_m.group(1)) if name_m else None
    years = name_m.group(2).strip() if name_m else None

    summary_m = SUMMARY_RE.search(html)
    summary = strip_tags(summary_m.group(1)) if summary_m else None

    birth = {"date": None, "place": None, "raw": None}
    death = {"date": None, "place": None, "raw": None}
    if summary:
        birth = _parse_birth(summary)
        death = _parse_death(summary, birth["place"])

    return {
        "composer_url": url,
        "title": f"{name} ({years})" if name and years else name,
        "name": name,
        "years": years,
        "description": summary,
        "birth": birth,
        "death": death,
        "biography": _parse_field(html, "biography"),
        "publications": _parse_field(html, "publications"),
        "bibliography": _parse_field(html, "bibliography"),
        "sources": _parse_field(html, "sources"),
        "links": _parse_links(html),
        "works_summary": (lambda m: strip_tags(m.group(1)) if m else None)(WORKS_SUMMARY_RE.search(html)),
        "works": _parse_works(html),
        "slug": slug,
    }


def _csv_row(data: dict) -> dict:
    return {
        "name": data["name"] or "",
        "birth_date": data["birth"]["date"] or "",
        "birth_place": data["birth"]["place"] or "",
        "death_date": data["death"]["date"] or "",
        "death_place": data["death"]["place"] or "",
        "url": data["composer_url"],
    }


CSV_FIELDS = ["name", "birth_date", "birth_place", "death_date", "death_place", "url"]


def _build_csv_from_saved_json():
    """Standalone step, no fetching: reads every already-saved
    data/Swedish_Heritage/*.json and (re)writes the summary CSV from
    them. Lets the CSV be regenerated (e.g. after improving the birth/
    death regexes) without re-hitting the site."""
    json_files = sorted(OUT_DIR.glob("*.json"))
    if not json_files:
        raise click.ClickException(f"No JSON files found in {OUT_DIR} -- run a fetch first (without --csv).")
    rows = [_csv_row(json.loads(p.read_text(encoding="utf-8"))) for p in json_files]
    with open(DEFAULT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows (from {len(json_files)} saved JSON files) to {DEFAULT_CSV_PATH}")


@click.command("swedish-heritage")
@click.option("--csv", "csv_only", is_flag=True, help=f"Don't fetch -- just (re)build {DEFAULT_CSV_PATH} from already-saved JSON files.")
@click.option("--limit", type=int, default=None, help="Only fetch the first N composers (for testing).")
def swedish_heritage_command(csv_only: bool, limit: int | None):
    if csv_only:
        _build_csv_from_saved_json()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Collecting composer links from the index page...")
    composers = collect_composer_links()
    if limit:
        composers = composers[:limit]
    print(f"{len(composers)} composers found")

    no_dates = []
    failed = []
    skipped = 0
    for i, entry in enumerate(composers, 1):
        if (OUT_DIR / f"{entry['slug']}.json").exists():
            skipped += 1
            continue
        try:
            html = fetch_bytes(entry["url"], USER_AGENT).decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            # A page listed in the index can still genuinely 404 on the
            # site's own end (found via andren-adolf, which 302-redirects
            # to /404) -- skip it and keep going rather than losing the
            # rest of the run over one broken link.
            print(f"  {entry['slug']}: fetch failed ({e}), skipping")
            failed.append(entry["slug"])
            continue

        data = parse_composer_page(html, entry["slug"], entry["url"])
        (OUT_DIR / f"{entry['slug']}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not data["birth"]["date"] and not data["death"]["date"]:
            no_dates.append(data["name"] or entry["slug"])

        if i % 20 == 0:
            print(f"  ...{i}/{len(composers)}", flush=True)
        time.sleep(0.3)

    print(f"Skipped (already fetched): {skipped}")
    print(f"JSON files saved for {len(composers) - len(failed) - skipped}/{len(composers)} composers in {OUT_DIR}")
    if failed:
        print(f"Failed to fetch ({len(failed)}): {', '.join(failed)}")
    print(f"Composers with no parseable birth or death date: {len(no_dates)}")
    for name in no_dates:
        print(f"  {name}")


if __name__ == "__main__":
    swedish_heritage_command()

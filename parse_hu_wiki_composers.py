"""Parse the Hungarian Wikipedia "list of Hungarian composers" wikitext
(zeneszerzok_hu_wiki.txt, saved from hu.wikipedia.org) into a CSV compatible
with load_composers.py's rows_for_csv (article, name, birth, death,
nationality).

Each entry looks like one of:
    *[[Ábrahám Pál]] (Apatin, 1892. november 2. – Hamburg, 1960. május 6.)
    *[[Ábrányi Emil (zeneszerző)|Ábrányi Emil]] (Budapest, 1882. ... – ...)
    *Ajtony Csaba (Budapest, 1976. szeptember 30. – )   -- no WP article
    *[[Berta István Angel]]                              -- no birth/death

`article` is the hu.wikipedia.org link target (used later as a
composer_wikilinks language='hu' title); `name` is the display name, in
Hungarian surname-first order.
"""
import csv
import re

SOURCE = "zeneszerzok_hu_wiki.txt"
DEST = "data/composers_Hungarian.csv"

# Era isn't derivable from the source list itself (it spans everything from
# the 1500s to today), so it's blank by default and only overridden here for
# composers manually identified as Baroque. Keyed by `article` (the hu wiki
# link target), since that's what's actually in the parsed rows -- e.g.
# "Johann Sigismund Kusser" is the international name; the hu list has him as
# "Kusser János Zsigmond".
ERA_OVERRIDES = {
    "Esterházy Pál (nádor)": "Baroque",
    "Kusser János Zsigmond": "Baroque",
    "Bengraf József": "Classical-era",
    "Druschetsky Georg": "Classical-era",
    "Fusz János": "Classical-era",
    "Istvánffy Benedek": "Classical-era",
    "Lavotta János": "Classical-era",
    "Menner Bernát": "Classical-era",
    "Ruzitska Ignác": "Classical-era",
    "Spech János": "Classical-era",
}

BULLET_RE = re.compile(r"^\*\s*")
WIKILINK_RE = re.compile(r"^\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REF_RE = re.compile(r"<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# A year is 3-4 digits (matches load_composers.py's own YEAR pattern), with
# an optional immediately-trailing '?' for sourced-as-uncertain years, and an
# optional Hungarian qualifier word following it ("körül" = circa,
# "után" = after, "előtt" = before).
YEAR_RE = re.compile(r"(\d{3,4})(\?)?\s*(körül|után|előtt)?")


def clean_line(line):
    line = REF_RE.sub("", line)
    line = COMMENT_RE.sub("", line)
    return line.strip()


def format_year(year, uncertain, qualifier):
    if qualifier == "körül":
        return f"c. {year}"
    if qualifier == "után":
        return f"after {year}"
    if qualifier == "előtt":
        return f"before {year}"
    return f"{year}?" if uncertain else year


def parse_dates(rest):
    """Extract (birth, death) formatted strings from the text following a
    composer's name, e.g. " (Budapest, 1882. szeptember 22. – Budapest,
    1970. február 11.)". Order of appearance is trusted for birth vs death.
    """
    years = YEAR_RE.findall(rest)
    if not years:
        return "", ""
    birth = format_year(*years[0])
    death = format_year(*years[1]) if len(years) > 1 else ""
    return birth, death


def parse_entry(line):
    line = BULLET_RE.sub("", line, count=1)
    line = clean_line(line)
    if not line:
        return None

    m = WIKILINK_RE.match(line)
    if m:
        article = m.group(1).strip()
        name = (m.group(2) or article).strip()
        rest = line[m.end():]
    else:
        # No [[wiki link]] on this line -- no WP article, but still a
        # composer entry. Name is whatever precedes the first '('.
        article = ""
        paren_idx = line.find("(")
        name = (line[:paren_idx] if paren_idx != -1 else line).strip().rstrip(",")
        rest = line[paren_idx:] if paren_idx != -1 else ""

    if not name:
        return None

    birth, death = parse_dates(rest)
    return {"article": article, "name": name, "birth": birth, "death": death}


def main():
    rows = []
    skipped = 0
    with open(SOURCE, encoding="utf-8") as f:
        for raw_line in f:
            if not raw_line.startswith("*"):
                continue
            entry = parse_entry(raw_line)
            if entry is None:
                skipped += 1
                continue
            rows.append(entry)

    matched_overrides = set()
    with open(DEST, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["article", "name", "birth", "death", "nationality", "era"])
        writer.writeheader()
        for row in rows:
            era = ERA_OVERRIDES.get(row["article"], "")
            if era:
                matched_overrides.add(row["article"])
            writer.writerow({**row, "nationality": "Hungarian", "era": era})

    no_article = sum(1 for r in rows if not r["article"])
    no_birth = sum(1 for r in rows if not r["birth"])
    print(f"Wrote {len(rows)} rows to {DEST} ({skipped} bullet lines skipped)")
    print(f"  {no_article} with no WP article, {no_birth} with no birth year")

    unmatched = set(ERA_OVERRIDES) - matched_overrides
    if unmatched:
        print(f"  WARNING: era override(s) not found in the source list: {sorted(unmatched)}")


if __name__ == "__main__":
    main()
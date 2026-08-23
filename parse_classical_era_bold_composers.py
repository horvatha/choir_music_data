"""One-off fix: List_of_Classical-era_composers.wiki has 63 bullet entries
written in Wikipedia bold markup (`* '''[[Name]]''' (birth-death)`, used by
the source page to highlight the "prominent composers" it calls out in its
own intro paragraph) instead of the plain `* [[Name]] (birth-death)` every
other entry -- and every other era's wiki file -- uses. Whatever process
originally turned this wiki file into composers_Classical-era.csv never
handled the bold wrapper, so all 63 -- including Haydn, Mozart, Salieri,
Clementi, Cimarosa and Paisiello, who have no other era source and so are
completely absent from the DB -- were silently dropped.

This appends the 63 missing rows to composers_Classical-era.csv (it does
not touch the other ~682 already-correct rows). Composers who already exist
via another era's CSV (most of these -- Bach, Handel, Vivaldi, ...) just
gain a second Classical-era tag once load_composers.py is rerun, since
composer_eras is many-to-many and its insert is ON CONFLICT DO NOTHING.

Usage:
    python3 parse_classical_era_bold_composers.py
"""
import re

WIKI_PATH = "List_of_Classical-era_composers.wiki"
CSV_PATH = "data/eras/composers_Classical-era.csv"

# '''[[Article|Display]]''' or '''[[Article]]''', optionally followed by
# other wikitext (e.g. Leclair's ''l'aîné'' nickname) before the (birth-death).
BOLD_LINE_RE = re.compile(
    r"^\*\s*'''\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'''.*?\(([^)]+)\)\s*$"
)
YEAR_RE = re.compile(r"(c\.\s*)?(\d{3,4})")


def parse_years(raw: str) -> tuple[str, str]:
    """'1671–1751' -> ('1671', '1751'); 'c. 1750–1792' -> ('c. 1750', '1792')."""
    parts = re.split(r"[–-]", raw)
    if len(parts) != 2:
        raise ValueError(f"can't split birth-death range: {raw!r}")
    birth_prefix, death_prefix = "", ""
    if "c." in parts[0]:
        birth_prefix = "c. "
    if "c." in parts[1]:
        death_prefix = "c. "
    birth = birth_prefix + YEAR_RE.search(parts[0]).group(2)
    death = death_prefix + YEAR_RE.search(parts[1]).group(2)
    return birth, death


def main():
    with open(WIKI_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()

    rows = []
    for line in lines:
        m = BOLD_LINE_RE.match(line)
        if not m:
            continue
        article, display, years = m.groups()
        name = (display or article).strip()
        birth, death = parse_years(years)
        rows.append((article.strip(), name, birth, death))

    print(f"Parsed {len(rows)} bold entries")

    with open(CSV_PATH, "a", encoding="utf-8") as f:
        for article, name, birth, death in rows:
            f.write(f"{article},{name},{birth},{death},Classical-era\n")

    print(f"Appended {len(rows)} rows to {CSV_PATH}")


if __name__ == "__main__":
    main()

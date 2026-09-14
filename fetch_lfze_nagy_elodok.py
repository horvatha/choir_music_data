"""Crawl the Liszt Academy's "Nagy elodok" (great predecessors) biographical
pages (https://lfze.hu/nagy-elodok), save every person's article as markdown,
save a picture for the ones classified as composers, and write a CSV of
(name, link, language, author) for that composer subset.

Everyone listed there is a former student/faculty member of the Academy in
some field -- performers, conductors, musicologists, composers, and so on.
This script's "is this a composer" check looks for the "zeneszerz" word stem
(zeneszerzo/zeneszerzes/...) in the *first* biography paragraph, since that's
where these pages state a person's field(s), either as an explicit label
("Zeneszerzo, zeneszerzestanar.") or within the opening narrative sentence.
People where the stem only shows up later in the article (e.g. a mention of
their composition teacher, or a career pivot mentioned mid-bio) are reported
separately as "uncertain" for a human to check, rather than included
automatically.

Markdown files (one per person, everyone, not just composers) and pictures
(composers only) are written into choir_music_data/lfze/, named after the
page's own URL slug (e.g. bartok-bela-1861.md / .jpg) so text and picture
pair up 1:1 and match the source page unambiguously. Pictures are fetched at
their original size, not the "_focuspoint_WxHpx" pre-cropped thumbnail the
page itself displays, by stripping that suffix from the image path (falling
back to the cropped version if the plain path 404s).

Usage:
    python3 fetch_lfze_nagy_elodok.py composers_lfze_nagy_elodok.csv
"""
import csv
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "choir_music_data-lfze-fetch/1.0 (personal research script)"
INDEX_URL = "https://lfze.hu/nagy-elodok"
# Confirmed directly against the site's own letter navigation -- no q/x/y.
LETTERS = list("abcdefghijklmnoprstuvwz")
LFZE_DIR = Path(__file__).resolve().parent / "lfze"

LINK_RE = re.compile(r'href="(/nagy-elodok/[a-z0-9-]+)"')
NAME_RE = re.compile(r"<h1>(.*?)</h1>", re.DOTALL)
ARTICLE_RE = re.compile(r'<article>(.*?)<div class="facebook-button">', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
AUTHOR_RE = re.compile(r'text-align:\s*right;?"[^>]*>\s*(?:<em>)?([^<]+?)(?:</em>)?\s*</(?:div|p)>')
PICTURE_RE = re.compile(r'src="(/data/lexikon/[^"]+)"')
FOCUSPOINT_SUFFIX_RE = re.compile(r"_focuspoint_\d+x\d+(?=\.\w+$)")


def fetch(url: str, retries: int = 5) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  {url}: network error, retrying in {wait}s...")
            time.sleep(wait)


def strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html)).strip()


def collect_person_links() -> dict[str, str]:
    people = {}
    for letter in LETTERS:
        html = fetch(f"{INDEX_URL}?letter={letter}").decode("utf-8")
        for path in LINK_RE.findall(html):
            slug = path.rsplit("/", 1)[-1]
            people.setdefault(slug, path)
        time.sleep(0.3)
    return people


def parse_person_page(html: str):
    name_m = NAME_RE.search(html)
    name = strip_tags(name_m.group(1)) if name_m else None

    picture_m = PICTURE_RE.search(html)
    picture_path = picture_m.group(1) if picture_m else None

    article_m = ARTICLE_RE.search(html)
    article_html = article_m.group(1) if article_m else ""

    author_m = AUTHOR_RE.search(article_html)
    author = author_m.group(1).strip() if author_m else None

    raw_paragraphs = re.split(r"</(?:div|p|h1)>", article_html)
    paragraphs = [strip_tags(p) for p in raw_paragraphs]
    paragraphs = [p for p in paragraphs if p]

    # paragraphs[0] is the <h1> name (redundant with `name` above), paragraphs[1]
    # is the "birthplace, date - death place, date" line.
    birth_death = paragraphs[1] if len(paragraphs) > 1 else ""
    bio_paragraphs = paragraphs[2:]
    # The last paragraph is the right-aligned author byline, already captured
    # separately above -- drop it from the body so it isn't duplicated.
    if bio_paragraphs and author and bio_paragraphs[-1] == author:
        bio_paragraphs = bio_paragraphs[:-1]

    return name, birth_death, author, bio_paragraphs, picture_path


def save_markdown(slug: str, name: str, url: str, birth_death: str, author: str, bio_paragraphs: list[str]):
    lines = [f"# {name}", ""]
    if birth_death:
        lines += [birth_death, ""]
    for para in bio_paragraphs:
        lines += [para, ""]
    if author:
        lines += [f"*{author}*", ""]
    lines += [f"Source: {url}"]
    (LFZE_DIR / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


def save_picture(slug: str, picture_path: str) -> bool:
    original_path = FOCUSPOINT_SUFFIX_RE.sub("", picture_path)
    ext = original_path.rsplit(".", 1)[-1]
    for candidate in (original_path, picture_path):
        candidate_url = f"https://lfze.hu{urllib.parse.quote(candidate, safe='/')}"
        try:
            data = fetch(candidate_url)
        except Exception:
            continue
        (LFZE_DIR / f"{slug}.{ext}").write_bytes(data)
        return True
    return False


def main():
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <output.csv>")
    dest = sys.argv[1]
    LFZE_DIR.mkdir(exist_ok=True)

    print("Collecting person links from the letter index...")
    people = collect_person_links()
    print(f"{len(people)} people found")

    composers = []
    uncertain = []
    others = 0
    pictures_saved = 0
    pictures_missing = []

    for i, (slug, path) in enumerate(sorted(people.items()), 1):
        url = f"https://lfze.hu{path}"
        html = fetch(url).decode("utf-8")
        name, birth_death, author, bio_paragraphs, picture_path = parse_person_page(html)
        save_markdown(slug, name, url, birth_death, author, bio_paragraphs)

        first_para = bio_paragraphs[0] if bio_paragraphs else ""
        rest = " ".join(bio_paragraphs[1:])
        is_composer = bool(re.search(r"zeneszerz", first_para, re.IGNORECASE))

        if is_composer:
            composers.append({"name": name, "link": url, "language": "hu", "author": author or ""})
            if picture_path:
                time.sleep(0.2)
                if save_picture(slug, picture_path):
                    pictures_saved += 1
                else:
                    pictures_missing.append(name)
            else:
                pictures_missing.append(name)
        elif re.search(r"zeneszerz", rest, re.IGNORECASE):
            uncertain.append((name, url))
        else:
            others += 1

        if i % 20 == 0:
            print(f"  ...{i}/{len(people)}")
            with open(dest, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["name", "link", "language", "author"])
                writer.writeheader()
                writer.writerows(composers)
        time.sleep(0.3)

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "link", "language", "author"])
        writer.writeheader()
        writer.writerows(composers)

    print(f"\nWrote {len(composers)} composer rows to {dest}")
    print(f"Markdown files saved for all {len(people)} people in {LFZE_DIR}")
    print(f"Pictures saved for composers: {pictures_saved}")
    print(f"Composers with no picture available: {len(pictures_missing)}")
    for name in pictures_missing:
        print(f"  {name}")
    print(f"Not composers (no 'zeneszerz' mention anywhere): {others}")
    print(f"Uncertain ('zeneszerz' only outside the first paragraph) -- review by hand: {len(uncertain)}")
    for name, url in uncertain:
        print(f"  {name}: {url}")


if __name__ == "__main__":
    main()

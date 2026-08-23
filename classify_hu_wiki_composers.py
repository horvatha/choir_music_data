"""Flag composers_Hungarian.csv rows that are probably pop/rock/light-music
figures rather than concert (classical/art) music composers, using each
composer's hu.wikipedia.org category membership -- fetched via the MediaWiki
API (structured data, not HTML scraping).

Heuristic, not a verdict: a composer is flagged "pop" if any of their
Wikipedia categories matches a light-music/performer signal (see
NEGATIVE_PATTERNS below), e.g. "Kategória:Magyar könnyűzenei előadók" for
Presser Gábor. Composers with no such category (e.g. Berkesi Sándor, who has
"Magyar karnagyok" and "Liszt Ferenc-díjasok" but nothing pop-flavored) are
left unflagged. This gets most cases right but not all -- read the output
and adjust ERA_OVERRIDES-style exceptions by hand for the ones it misses.

Results are cached in hu_wiki_categories_cache.json (article -> category
list) so reruns don't refetch. Adds two columns to composers_Hungarian.csv:
`flag` (pop / not_found / no_article / blank) and `flag_reason` (the
matching category, for audit).
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request

SOURCE = "data/composers_Hungarian.csv"
CACHE_FILE = "hu_wiki_categories_cache.json"
API_URL = "https://hu.wikipedia.org/w/api.php"
USER_AGENT = "choir_music_data-composer-classifier/1.0 (personal research script)"
BATCH_SIZE = 20

NEGATIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"könnyűzenei",
        r"rockzenész",
        r"popzenész",
        r"dzsesszzenész",
        r"metálzenész",
        r"diszkó",
        r"énekes",
        r"dalszerző",
    ]
]


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)


def fetch_categories(titles):
    """Fetch {title: category_list | None} for up to BATCH_SIZE titles.
    None means the page wasn't found (missing/typo'd/deleted).
    """
    result = {t: None for t in titles}
    params = {
        "action": "query",
        "format": "json",
        "prop": "categories",
        "cllimit": "500",
        "redirects": "1",
        "titles": "|".join(titles),
    }
    while True:
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 4:
                    raise
                wait = 2 ** (attempt + 2)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)

        query = data.get("query", {})
        redirects = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages = query.get("pages", {})
        for page in pages.values():
            title = page.get("title")
            # map back through any redirect(s) to the title we were asked for
            requested = title
            for src, dst in redirects.items():
                if dst == title:
                    requested = src
            cats = [c["title"] for c in page.get("categories", [])]
            if "missing" in page:
                result[requested] = None
            else:
                result.setdefault(requested, [])
                result[requested] = (result[requested] or []) + cats

        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
    return result


def classify(categories):
    if categories is None:
        return "not_found", ""
    for cat in categories:
        for pattern in NEGATIVE_PATTERNS:
            if pattern.search(cat):
                return "pop", cat
    return "", ""


def main():
    with open(SOURCE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cache = load_cache()
    titles_needed = sorted({
        r["article"] for r in rows if r["article"] and r["article"] not in cache
    })

    for i in range(0, len(titles_needed), BATCH_SIZE):
        batch = titles_needed[i:i + BATCH_SIZE]
        print(f"Fetching categories {i + 1}-{i + len(batch)} of {len(titles_needed)}...")
        cache.update(fetch_categories(batch))
        save_cache(cache)
        time.sleep(1.5)

    counts = {"pop": 0, "not_found": 0, "no_article": 0, "": 0}
    for row in rows:
        if not row["article"]:
            flag, reason = "no_article", ""
        else:
            flag, reason = classify(cache.get(row["article"]))
        row["flag"] = flag
        row["flag_reason"] = reason
        counts[flag] += 1

    fieldnames = list(rows[0].keys())
    with open(SOURCE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} rows: {counts['pop']} flagged pop/light-music, "
          f"{counts['not_found']} article not found, {counts['no_article']} with no article, "
          f"{counts['']} unflagged")
    print("\nFlagged as pop/light-music:")
    for row in rows:
        if row["flag"] == "pop":
            print(f"  {row['name']} ({row['flag_reason']})")


if __name__ == "__main__":
    main()
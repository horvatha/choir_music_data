"""Shared HTTP-fetch helpers for this repo's page-scraping scripts
(fetch_lfze_nagy_elodok.py, fetch_swedish_heritage.py, ...) -- a plain
urllib GET with retry/backoff on network errors, plus an HTML
tag-stripping helper for turning a chunk of markup into plain text.

Kept deliberately minimal: no HTML parsing library dependency, since
every caller so far parses its own page structure with regex tailored
to that one site (each site's markup is different enough -- and each
script's needs specific enough -- that a shared parser wouldn't buy
much; only the network/text plumbing is actually common).
"""
import re
import time
import urllib.error
import urllib.request

_TAG_RE = re.compile(r"<[^>]+>")


def fetch(url: str, user_agent: str, retries: int = 5, timeout: int = 15) -> bytes:
    """GET url, retrying with exponential backoff on network error.

    user_agent is a required argument, not a shared default -- every
    caller should identify itself and its purpose (e.g.
    "choir_music_data-lfze-fetch/1.0 (personal research script)"), per
    basic scraping etiquette, and the right string differs per site/
    script."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            # A real response from the server (404, a redirect loop, ...)
            # -- a permanent condition retrying won't fix, unlike a
            # transient connection/timeout failure. Raise immediately
            # instead of burning the full backoff schedule on a page
            # that's simply broken on the site's own end (found via
            # swedishmusicalheritage.com/composers/andren-adolf/, listed
            # in the index but 302-redirecting into a loop).
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  {url}: network error, retrying in {wait}s...")
            time.sleep(wait)


def strip_tags(html: str) -> str:
    """Collapse a chunk of HTML down to whitespace-normalized plain text."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()

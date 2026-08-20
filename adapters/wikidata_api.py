"""HTTP adapter for Wikidata/Wikipedia's live APIs -- every function here
either makes a network call directly or (use_socks_proxy) exists purely to
configure how the ones that do will route. Pure data-extraction logic that
operates on an already-fetched entity dict (extract_relationships,
extract_attributes, extract_dates, ...) lives in
fetch_wikidata_relationships.py instead, not here -- that code makes no
network calls of its own.
"""
import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from adapters import wikidata_entities_store

# WIKIDATA_CONTACT_EMAIL is optional -- set it in your shell (never
# hardcoded/committed) to identify yourself to Wikimedia per their API
# etiquette guidelines; omitted from the User-Agent entirely if unset.
_contact = os.environ.get("WIKIDATA_CONTACT_EMAIL")
USER_AGENT = (
    f"choir_music_data-wikidata-fetch/1.0 (personal research script; {_contact})"
    if _contact
    else "choir_music_data-wikidata-fetch/1.0 (personal research script)"
)

# Every composer gets these, regardless of nationality. "ru" is here
# unconditionally (not keyed off a "Russian"/"Soviet" nationality tag like
# fetch_wikidata_relationships.NATIVE_LANGUAGE_BY_NATIONALITY) because
# plenty of composers who lived and worked under the Russian Empire or
# Soviet Union are tagged with their own ethnic nationality only
# (Armenian, Georgian, Ukrainian, Azerbaijani, Estonian, ...) with no
# "Soviet"/"Russian" tag anywhere to key off of, yet they commonly have a
# distinct, meaningful Russian name from operating in Russian as the
# administrative lingua franca (e.g. Aram Khachaturian: tagged only
# "Armenian", died in Moscow under Soviet citizenship, has a proper
# Russian Wikipedia name). Detecting this from place-of-birth/death text
# is unreliable (many wouldn't literally say "Moscow"/"Leningrad"/
# "Soviet"), so it's simpler and safer to just always ask -- Wikidata
# omits the key gracefully when no Russian label exists.
BASE_LABEL_LANGUAGES = ["en", "hu", "ru"]


def use_socks_proxy(port=1080):
    """Route every socket connection *made from here on* through a local
    SOCKS5 proxy (e.g. `ssh -D <port> ...`) -- lets a second fetch instance
    exit through a different IP (the SSH server's) so it isn't sharing the
    same Wikidata/Wikipedia rate-limit bucket as one running directly.

    Must be called AFTER any Postgres connection is already open: this
    monkey-patches socket.socket globally (there's no narrower way to make
    stdlib urllib SOCKS-aware without switching HTTP libraries), so calling
    it first would route the DB connection through the tunnel too, which
    isn't wanted -- Postgres should stay direct. psycopg2 keeps using
    whatever real socket it already opened before this call; only sockets
    opened afterward (i.e. this script's own HTTP requests) are affected.

    Requires PySocks (`pip install PySocks`) -- not a dependency of the
    rest of this repo, only needed for --through-vm."""
    import socket

    import socks
    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", port)
    socket.socket = socks.socksocket


def api_get(url, params, retries=5):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 2)
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
        except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
            # Transient network blips (socket read timeouts, connection
            # resets, DNS hiccups) -- over a run of hundreds of composers
            # against two different APIs, these are expected occasionally
            # and shouldn't crash the whole run, unlike a genuine HTTP error
            # response which usually means something is actually wrong.
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 2)
            print(f"  network error ({e}), retrying in {wait}s...")
            time.sleep(wait)


def get_qid(wikilinks):
    """Try each wikilink (preferring 'en') until one resolves to a Wikidata QID."""
    ordered = sorted(wikilinks, key=lambda w: w[0] != "en")
    for language, title in ordered:
        data = api_get(
            f"https://{language}.wikipedia.org/w/api.php",
            {"action": "query", "format": "json", "prop": "pageprops",
             "titles": title, "ppprop": "wikibase_item"},
        )
        for page in data.get("query", {}).get("pages", {}).values():
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                return qid
    return None


def get_entity(qid, languages, max_age_days=None):
    """A single entity's full labels|claims|sitelinks, for `languages`.

    max_age_days is opt-in and None by default -- when None, this *always*
    makes a live request, exactly as before: fetch_composers.py's --ids
    relies on that ("this never skips get_entity() itself" -- see its
    _fetch_one() docstring) to guarantee a forced re-fetch actually re-
    fetches, so a cache-trusts-forever default here would silently break
    that guarantee. Passing a numeric max_age_days opts a caller into
    checking wikidata_entities first and skipping the live call when a
    fresh-enough row is already there."""
    if max_age_days is not None:
        cached = wikidata_entities_store.fetch_entities([qid], max_age_days=max_age_days)
        if qid in cached:
            return cached[qid]
    data = api_get(
        "https://www.wikidata.org/w/api.php",
        {"action": "wbgetentities", "format": "json", "ids": qid,
         "props": "labels|claims|sitelinks", "languages": "|".join(languages)},
    )
    entity = data.get("entities", {}).get(qid)
    if entity is not None:
        wikidata_entities_store.store_entity(qid, entity)
    return entity


def get_labels(qids, languages=BASE_LABEL_LANGUAGES):
    """Batch-resolve display labels for up to 50 QIDs at a time. Referenced
    people (fathers/teachers/students/...) aren't composers we have a
    nationality for, so this only asks for the base languages unless told
    otherwise.

    Always additionally requests "mul" (Wikidata's language-independent
    label, used for e.g. a person's name when it doesn't change across
    languages/scripts) -- some entities carry *only* a "mul" label and no
    "en"/"hu"/"ru" one at all (e.g. Bedřich Smetana's mother, Q140302264),
    which without this silently fell back to the raw QID as the "name"."""
    labels = {}
    qids = list(qids)
    request_languages = list(languages) + ["mul"]
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "|".join(request_languages)},
        )
        for qid, entity in data.get("entities", {}).items():
            entity_labels = entity.get("labels", {})
            preferred = entity_labels.get("en") or next(iter(entity_labels.values()), None)
            labels[qid] = preferred["value"] if preferred else qid
        time.sleep(0.3)
    return labels


def get_hu_labels(qids):
    """Batch-resolve *specifically* Hungarian labels for up to 50 QIDs at a
    time. Unlike get_labels(), which always returns something (falling
    back through en/other languages/the QID itself), this only returns a
    QID that actually has an 'hu' label on Wikidata -- a QID missing from
    the result means no Hungarian name exists there, not "not fetched
    yet", so callers can tell the two apart."""
    labels = {}
    qids = list(qids)
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        data = api_get(
            "https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
             "props": "labels", "languages": "hu"},
        )
        for qid, entity in data.get("entities", {}).items():
            hu_label = entity.get("labels", {}).get("hu", {}).get("value")
            if hu_label:
                labels[qid] = hu_label
        time.sleep(0.3)
    return labels

"""Write-through cache for full raw Wikidata entities, keyed by QID, stored
as JSONB in a separate "wikidata_entities" Postgres database (see
schema_wikidata_entities.sql) -- not the main "composers" app database.

This is strictly supplementary to the existing wikidata_relationships.json
cache: every fetch/backfill script keeps reading/writing that file exactly
as before. store_entity() is called from get_entity() in
fetch_wikidata_relationships.py as an additional side effect, so raw
entities accumulate automatically on every ordinary fetch without any
caller needing to change. A failure here (DB unreachable, database not
yet created, etc.) must never break the primary pipeline -- it's caught
and warned about once per process, not raised.
"""

import os

import psycopg2
import psycopg2.extras

_UPSERT_SQL = """
    INSERT INTO entities (qid, entity, fetched_at)
    VALUES (%(qid)s, %(entity)s, now())
    ON CONFLICT (qid) DO UPDATE SET entity = EXCLUDED.entity, fetched_at = EXCLUDED.fetched_at
"""

_conn = None
_disabled = False


def _get_connection():
    global _conn
    if _conn is None:
        # Same server/user as the main DB (standard libpq env vars), just a
        # different database -- WIKIDATA_ENTITIES_PGDATABASE overrides only
        # dbname, no separate credentials to manage.
        dbname = os.environ.get("WIKIDATA_ENTITIES_PGDATABASE", "wikidata_entities")
        _conn = psycopg2.connect(dbname=dbname)
        _conn.autocommit = True
    return _conn


def store_entity(qid: str, entity: dict) -> None:
    global _disabled
    if _disabled:
        return
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, {"qid": qid, "entity": psycopg2.extras.Json(entity)})
    except Exception as error:
        print(f"wikidata_entities_store: could not store raw entities ({error}); continuing without it.")
        _disabled = True


def fetch_entities(qids) -> dict:
    """Bulk-read cached raw entities: {qid: entity} for whichever of the
    given QIDs already have a row. A QID missing from the result means
    "not cached", not an error -- callers fall back to a live fetch for
    it. Same failure-handling convention as store_entity()/warm_up(): a DB
    problem disables the cache for the rest of the process and returns {}
    rather than raising, so callers always have a safe, correct fallback
    (behave exactly as if nothing were cached)."""
    global _disabled
    if _disabled or not qids:
        return {}
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT qid, entity FROM entities WHERE qid = ANY(%s)", (list(qids),))
            return dict(cur.fetchall())
    except Exception as error:
        print(f"wikidata_entities_store: could not read cached entities ({error}); continuing without it.")
        _disabled = True
        return {}


def warm_up() -> None:
    """Opens the connection eagerly. Callers that monkey-patch socket.socket
    afterward (fetch_composers.py's --through-vm / use_socks_proxy()) must
    call this first -- store_entity() connects lazily on first use, which
    would otherwise happen from inside the per-composer fetch loop, after
    the proxy patch is already in effect, silently routing this DB
    connection through the SOCKS tunnel instead of straight to Postgres.
    Same failure handling as store_entity(): never raises."""
    global _disabled
    if _disabled:
        return
    try:
        _get_connection()
    except Exception as error:
        print(f"wikidata_entities_store: could not store raw entities ({error}); continuing without it.")
        _disabled = True

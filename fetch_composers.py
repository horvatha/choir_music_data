"""Fetch full Wikidata records (relationships, attributes, dates,
sitelinks, cross-language labels) for composers selected by --era,
--nationality, or --ids -- exactly one of the three. Writes into
wikidata_relationships.json under data["composers"], keyed by our own
composer_id; the file's keys double as the "already processed" list (for
--era/--nationality), so reruns are safe to stop/resume.

--era and --nationality skip composers already in the cache; --ids always
re-fetches every id given (matching each selector's original script) and
also always looks up the composer's nationality to extend the fetched
language set beyond BASE_LABEL_LANGUAGES, same as --era/--nationality --
the original fetch_wikidata_for_composer_ids.py never did this lookup,
which looked like an oversight rather than a deliberate choice, so this
merge fixes it rather than preserving the narrower behavior.

--era paces requests at 12s apart (Wikidata's sustained rate limit seems
to be ~5/minute; 12s/request stays under that without eating the
exponential backoff a faster pace triggers) -- --nationality/--ids keep
the original faster 0.3s pace, since sweeping a whole era's worth of
composers is a much larger, longer-running batch than a nationality group
or an explicit id list tends to be. Not harmonized; ported as-is.

--through-vm (only meaningful with --era): runs a second instance at the
same time as a normal run without the two colliding -- requests route
through a local SOCKS5 proxy (`ssh -D 1080 ...`) and new entries go to a
separate wikidata_relationships_vm.json instead of the shared file. See
merge_vm_fetch.py to fold that file's entries back in afterward.

--only (only meaningful with --era): restricts to composers who belong
*exclusively* to the given era(s), so two era sweeps can run concurrently
without both fetching the same transitional composer.

Usage:
    python3 fetch_composers.py --nationality Hungarian
    python3 fetch_composers.py --nationality Russian --nationality Soviet
    python3 fetch_composers.py --era Medieval --era Renaissance
    python3 fetch_composers.py --era 20th-century --through-vm
    python3 fetch_composers.py --era 20th-century --only --through-vm
    python3 fetch_composers.py --ids 7968 --ids 7971 --ids 7975
"""
import json
import time

import click
import psycopg2

from fetch_wikidata_relationships import (
    FETCH_COMPOSER_NATIONALITIES_SQL,
    OUTPUT_FILE,
    extract_attributes,
    extract_dates,
    extract_image,
    extract_relationships,
    extract_sitelinks,
    get_entity,
    get_labels,
    get_qid,
    label_languages_for,
    use_socks_proxy,
)

VM_OUTPUT_FILE = "wikidata_relationships_vm.json"

FETCH_WIKILINKS_SQL = "SELECT language, title FROM composer_wikilinks WHERE composer_id = %s"
FETCH_NAME_SQL = "SELECT name FROM composers WHERE id = %s"

FETCH_COMPOSERS_BY_NATIONALITY_SQL = """
    SELECT DISTINCT c.id, c.name
    FROM composers c
    JOIN composer_nationalities cn ON cn.composer_id = c.id
    JOIN nationalities n ON n.id = cn.nationality_id
    WHERE n.name = ANY(%s)
    ORDER BY c.id
"""

FETCH_COMPOSERS_BY_ERA_SQL = """
    SELECT DISTINCT c.id, c.name
    FROM composers c
    JOIN composer_eras ce ON ce.composer_id = c.id
    JOIN eras e ON e.id = ce.era_id
    WHERE e.name = ANY(%s)
    ORDER BY c.id
"""

# --only variant: excludes composers who have any era outside the given
# list -- e.g. `--era 20th-century --only` skips a composer tagged both
# Romantic-era and 20th-century, already covered by a Romantic-era run.
FETCH_COMPOSERS_BY_ERA_ONLY_SQL = """
    SELECT DISTINCT c.id, c.name
    FROM composers c
    JOIN composer_eras ce ON ce.composer_id = c.id
    JOIN eras e ON e.id = ce.era_id
    WHERE e.name = ANY(%s)
      AND NOT EXISTS (
          SELECT 1
          FROM composer_eras ce2
          JOIN eras e2 ON e2.id = ce2.era_id
          WHERE ce2.composer_id = c.id
            AND e2.name != ALL(%s)
      )
    ORDER BY c.id
"""


def _fetch_one(cur, composer_id, name, entries, languages):
    """Fetch one composer's full Wikidata record into `entries`. Returns
    True if an entity was actually fetched (vs. a no-wikilinks/no-QID/
    not-found short-circuit), so callers only sleep after a real request."""
    key = str(composer_id)
    cur.execute(FETCH_WIKILINKS_SQL, (composer_id,))
    wikilinks = cur.fetchall()
    if not wikilinks:
        entries[key] = {"name": name, "qid": None, "applied_to_db": True}
        return False

    qid = get_qid(wikilinks)
    if not qid:
        entries[key] = {"name": name, "qid": None, "applied_to_db": True}
        return False

    entity = get_entity(qid, languages)
    if entity is None:
        # QID resolved but the entity itself didn't come back -- a
        # Wikidata redirect (merged item) or a deleted item. Recorded so
        # a rerun doesn't keep retrying it forever.
        entries[key] = {"name": name, "qid": qid, "applied_to_db": True}
        print(f"  {composer_id} {name}: qid={qid} but entity not found (redirect/deleted?)")
        return False

    labels = {lang: v["value"] for lang, v in entity.get("labels", {}).items()}
    relationships = extract_relationships(entity)
    attributes = extract_attributes(entity)
    sitelinks = extract_sitelinks(entity)
    dates = extract_dates(entity)
    image = extract_image(entity)
    entries[key] = {
        "name": name, "qid": qid, "labels": labels,
        "relationships": relationships, "attributes": attributes,
        "sitelinks": sitelinks, "dates": dates, "applied_to_db": True,
        **image,
    }
    print(f"  {composer_id} {name}: qid={qid} labels={list(labels)} "
          f"relationships={list(relationships)} attributes={list(attributes)} "
          f"sitelinks={list(sitelinks)}")
    return True


def _resolve_referenced_labels(entries, label_cache):
    # Some older entries' "attributes" mix in plain-string summary fields
    # (e.g. "place_of_birth_text") alongside the QID lists -- iterating a
    # string yields characters, so `qs` must be an actual list before
    # being folded into the QID set.
    all_qids = {
        q for e in entries.values()
        for group in (e.get("relationships", {}), e.get("attributes", {}))
        for qs in group.values() if isinstance(qs, list)
        for q in qs
    }
    unresolved = [q for q in all_qids if q not in label_cache]
    if unresolved:
        print(f"Resolving labels for {len(unresolved)} referenced people/places/instruments...")
        label_cache.update(get_labels(unresolved))


def _fetch_by_selector(cur, composers, entries, label_cache, sleep):
    """Shared loop for --nationality/--era: skip composers already in
    `entries`, look up each one's nationality-derived language set."""
    already_done = 0
    for composer_id, name in composers:
        key = str(composer_id)
        if key in entries:
            already_done += 1
            continue

        cur.execute(FETCH_COMPOSER_NATIONALITIES_SQL, (composer_id,))
        composer_nationalities = [r[0] for r in cur.fetchall()]
        languages = label_languages_for(composer_nationalities)

        fetched = _fetch_one(cur, composer_id, name, entries, languages)
        if fetched:
            time.sleep(sleep)
            yield

    if already_done:
        print(f"{already_done} already known, skipped")


def _fetch_by_ids(cur, composer_ids, entries):
    """--ids always re-fetches every id given, regardless of whether it's
    already cached -- matches the original script's behavior."""
    for composer_id in composer_ids:
        cur.execute(FETCH_NAME_SQL, (composer_id,))
        row = cur.fetchone()
        if row is None:
            print(f"  {composer_id}: no such composer, skipping")
            continue
        name = row[0]

        cur.execute(FETCH_COMPOSER_NATIONALITIES_SQL, (composer_id,))
        composer_nationalities = [r[0] for r in cur.fetchall()]
        languages = label_languages_for(composer_nationalities)

        fetched = _fetch_one(cur, composer_id, name, entries, languages)
        if fetched:
            time.sleep(0.3)
            yield


def fetch(era, nationality, ids, through_vm, only):
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            output = json.load(f)
    except FileNotFoundError:
        output = {}
    entries = output.setdefault("composers", {})
    label_cache = output.setdefault("qid_labels", {})

    # VM mode only applies to --era: entries/label_cache above stay
    # read-only (checked to skip/reuse, never written or saved), and
    # everything new goes into a separate file so a normal run and a
    # through-vm run never race to write the same file.
    if through_vm:
        write_path = VM_OUTPUT_FILE
        try:
            with open(VM_OUTPUT_FILE, encoding="utf-8") as f:
                vm_output = json.load(f)
        except FileNotFoundError:
            vm_output = {}
        new_entries = vm_output.setdefault("composers", {})
        new_label_cache = vm_output.setdefault("qid_labels", {})
    else:
        write_path = OUTPUT_FILE
        vm_output = output
        new_entries = entries
        new_label_cache = label_cache

    def save():
        with open(write_path, "w", encoding="utf-8") as f:
            json.dump(vm_output, f, ensure_ascii=False, indent=1, sort_keys=True)

    conn = psycopg2.connect()
    # autocommit: these selectors only read from the DB. Without it, the
    # first SELECT opens a transaction that isn't committed until the
    # whole (very long, API-call-bound) run finishes, holding a lock that
    # blocks any concurrent schema change on the tables it reads.
    conn.autocommit = True
    if through_vm:
        # After connecting, not before -- see use_socks_proxy's docstring.
        use_socks_proxy()
    try:
        with conn.cursor() as cur:
            if nationality:
                cur.execute(FETCH_COMPOSERS_BY_NATIONALITY_SQL, (list(nationality),))
                composers = cur.fetchall()
                print(f"{len(composers)} composers for {list(nationality)}")
                runner = _fetch_by_selector(cur, composers, new_entries, new_label_cache, sleep=0.3)
            elif era:
                eras = list(era)
                if only:
                    cur.execute(FETCH_COMPOSERS_BY_ERA_ONLY_SQL, (eras, eras))
                else:
                    cur.execute(FETCH_COMPOSERS_BY_ERA_SQL, (eras,))
                composers = cur.fetchall()
                print(f"{len(composers)} composers for {eras}"
                      + (" (--only: excluding composers with other eras too)" if only else "")
                      + (f" (writing to {write_path})" if through_vm else ""))
                runner = _fetch_by_selector(cur, composers, new_entries, new_label_cache, sleep=12)
            else:
                runner = _fetch_by_ids(cur, list(ids), new_entries)

            for _ in runner:
                save()

            _resolve_referenced_labels(new_entries, {**label_cache, **new_label_cache} if through_vm else label_cache)
    finally:
        conn.close()

    save()
    print(f"\n{len(new_entries)} composers recorded in {write_path}")


@click.command("composers")
@click.option("--era", multiple=True, help="Select composers by era (repeatable). Mutually exclusive with --nationality/--ids.")
@click.option("--nationality", multiple=True, help="Select composers by nationality (repeatable). Mutually exclusive with --era/--ids.")
@click.option("--ids", multiple=True, type=int, help="Select composers by id (repeatable, always re-fetched). Mutually exclusive with --era/--nationality.")
@click.option("--through-vm", is_flag=True, help="Only with --era: route through a local SOCKS5 proxy and write to a separate VM output file.")
@click.option("--only", is_flag=True, help="Only with --era: exclude composers who also belong to an era outside the given list.")
def composers_command(era, nationality, ids, through_vm, only):
    """Fetch full Wikidata records for composers selected by --era, --nationality, or --ids."""
    selectors_given = sum(bool(x) for x in (era, nationality, ids))
    if selectors_given != 1:
        raise click.UsageError("Give exactly one of --era, --nationality, --ids.")
    if through_vm and not era:
        raise click.UsageError("--through-vm is only valid with --era.")
    if only and not era:
        raise click.UsageError("--only is only valid with --era.")
    fetch(era, nationality, ids, through_vm, only)


if __name__ == "__main__":
    composers_command()

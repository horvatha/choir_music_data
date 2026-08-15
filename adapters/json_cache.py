"""Generic read/write helpers for this repo's flat JSON cache files (e.g.
wikidata_relationships.json, wikidata_relationships_vm.json). Deliberately
knows nothing about "wikidata" or any specific filename -- callers own
which path they pass in, exactly as they did with the inline open()/
json.load()/json.dump() calls this replaces.

save_cache() writes to a fresh temp file and swaps it into place with
os.replace() rather than truncating the target file in place -- the old
open(path, "w") approach has a torn-read window between truncation and
the write finishing, during which any concurrent reader sees a partial,
invalid file (confirmed live against wikidata_relationships.json while
fetch_composers.py --ids was running: json.load() intermittently raised
JSONDecodeError). os.replace() is a single atomic directory-entry swap on
POSIX, so a reader's open() always resolves to either the fully-old or
fully-new inode, never a partial one -- see the temp file's own unique
name below for why this also holds up under two concurrent writers, not
just one writer racing one reader.

This does NOT fix the separate, pre-existing "two concurrent writers"
hazard documented in README.md's "Pipeline rules" (whichever finishes
last silently wins, discarding the other's progress) -- that's a data-loss
problem, not a torn-read problem, and needs actual coordination (this
repo's existing mitigation: route parallel runs to a separate file, merge
back later) rather than anything atomic-write alone can solve.
"""
import json
import os
import tempfile


def load_cache(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(path, data):
    directory = os.path.dirname(path) or "."
    # A unique-per-call temp name (not a fixed f"{path}.tmp") so two
    # processes calling save_cache() at the same time never share a temp
    # file either -- each writes its own, independent of the other, and
    # each swap is independently atomic (the last one to replace() simply
    # wins, matching the pre-existing "concurrent writers" semantics
    # noted above, rather than the two writes interleaving into garbage).
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise

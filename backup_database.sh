#!/usr/bin/env bash
set -euo pipefail

# --no-copy: dump only, skip the scp upload to the production server --
# for taking a local-only safety snapshot before testing a risky rerun
# (see CLAUDE.md's "Testing DB changes safely" section), not for syncing
# to production.
COPY=1
if [ "${1:-}" = "--no-copy" ]; then
    COPY=0
fi

CONTAINER=composers-pg
DB_USER=composers
DB_NAME=composers
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pg_dumps"
OUT_FILE="${OUT_DIR}/composers_backup_$(date +%Y%m%d_%H%M%S).dump"
REMOTE_HOST=pyedu.hu

mkdir -p "$OUT_DIR"

podman exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -f /tmp/composers_backup.dump
podman cp "$CONTAINER":/tmp/composers_backup.dump "$OUT_FILE"
podman exec "$CONTAINER" rm /tmp/composers_backup.dump

echo "Backup written to $OUT_FILE"

if [ "$COPY" -eq 0 ]; then
    echo "--no-copy: skipping upload to ${REMOTE_HOST}."
    exit 0
fi

echo "Uploading to ${REMOTE_HOST}:~/ ..."
scp "$OUT_FILE" "${REMOTE_HOST}:~/"

echo
echo "Uploaded. To restore on the server, SSH in and run:"
echo "  ssh ${REMOTE_HOST}"
echo "  restore_database.sh ~/$(basename "$OUT_FILE")"
# Standard libpq env vars for the local dev DB (composers-pg podman
# container, see podman_cmds/psql.txt). Source this, don't execute it --
# `export`ed vars in a subshell don't reach your interactive shell:
#
#   source pg_env.sh
#
# Every script in this repo reads these directly via psycopg2.connect()
# (no args) -- see CLAUDE.md: connection is always via env vars, never
# hardcoded in scripts.
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=composers
export PGUSER=composers
export PGPASSWORD=composers_dev

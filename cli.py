"""Single entry point for this repo's fetch/load/backfill commands.

python3 cli.py fetch composers --era Baroque
python3 cli.py fetch labels --entity instrument
python3 cli.py load names --entity instrument
python3 cli.py backfill cache --field dates

Each subcommand's own --help documents its options. Business logic lives
in the individual fetch_*.py/load_*.py/backfill_*.py modules -- this file
only wires them together.
"""
import click

from backfill_cache import cache_command
from fetch_candidate_people import candidates_command
from fetch_composer_names import composer_names_command
from fetch_composers import composers_command
from fetch_labels import labels_command
from load_names import names_command


@click.group()
def cli():
    pass


@cli.group()
def fetch():
    """Fetch data from Wikidata into wikidata_relationships.json."""


@cli.group()
def load():
    """Load cached Wikidata data into Postgres."""


@cli.group()
def backfill():
    """Patch missing/stale fields into the Wikidata cache."""


fetch.add_command(composers_command)
fetch.add_command(composer_names_command)
fetch.add_command(candidates_command)
fetch.add_command(labels_command)
load.add_command(names_command)
backfill.add_command(cache_command)


if __name__ == "__main__":
    cli()

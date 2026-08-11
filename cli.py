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


load.add_command(names_command)


if __name__ == "__main__":
    cli()

"""CLI entry point for hermes-mac."""

import click
from rich import print

from hermes_mac import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    """Hermes-mac: PC Personal Assistant."""
    pass


if __name__ == "__main__":
    main()
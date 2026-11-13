"""Command-line entry point: one command per pipeline stage."""

from pathlib import Path

import typer

from pipeline.fetch import fetch_dump

app = typer.Typer(help="Karachay-Balkar corpus pipeline.")


@app.callback()
def main() -> None:
    """Karachay-Balkar corpus pipeline."""


@app.command()
def fetch(
    date: str = typer.Option(..., help="Dump date, e.g. 20261101. Use a dated dump, not 'latest'."),
    wiki: str = typer.Option("krcwiki", help="Wikimedia project name."),
    raw_dir: Path = typer.Option(Path("data/raw"), help="Where raw files and the manifest live."),
) -> None:
    """Download a Wikipedia articles dump, verify it, and store it by content hash."""
    record = fetch_dump(wiki, date, raw_dir)
    typer.echo(f"{record['path']}  {record['size']} bytes  fetched {record['fetched_at']}")

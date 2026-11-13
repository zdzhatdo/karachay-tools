"""Command-line entry point: one command per pipeline stage."""

from pathlib import Path

import typer

from pipeline.extract import extract_dump
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


@app.command()
def extract(
    dump: Path = typer.Argument(..., help="A raw dump stored by `fetch`, e.g. data/raw/<sha256>.xml.bz2."),
    out_dir: Path = typer.Option(Path("data/extracted"), help="Where extracted JSONL files go."),
) -> None:
    """Turn a stored Wikipedia dump into plain-text articles (one JSON line per article)."""
    out, stats = extract_dump(dump, out_dir)
    typer.echo(out)
    for name, count in stats.most_common():
        typer.echo(f"  {name}: {count}")

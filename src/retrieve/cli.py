"""`netsci retrieve ...` — fetch raw source data."""

from __future__ import annotations

import typer

from src.retrieve.openflights import fetch as fetch_openflights

app = typer.Typer(help="Module 1: data retrieval.")


@app.command()
def openflights() -> None:
    """Download OpenFlights airports + routes (the air layer)."""
    out = fetch_openflights()
    typer.echo(f"retrieved OpenFlights -> {out}")

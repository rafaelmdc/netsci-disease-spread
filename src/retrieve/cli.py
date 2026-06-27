"""`netsci retrieve ...` — fetch raw source data."""

from __future__ import annotations

import typer

from src.retrieve.geonames import fetch as fetch_geonames
from src.retrieve.openflights import fetch as fetch_openflights
from src.retrieve.osm_ferries import fetch as fetch_ferries

app = typer.Typer(help="Module 1: data retrieval.")

_FORCE = typer.Option(False, "--force", "-f", help="Re-download even if cached.")


@app.command()
def openflights(force: bool = _FORCE) -> None:
    """Download OpenFlights airports + routes (the air layer)."""
    typer.echo(f"retrieved OpenFlights -> {fetch_openflights(force=force)}")


@app.command()
def geonames(force: bool = _FORCE) -> None:
    """Download GeoNames cities1000 (the canonical city node set)."""
    typer.echo(f"retrieved GeoNames cities -> {fetch_geonames(force=force)}")


@app.command()
def ferries(force: bool = _FORCE) -> None:
    """Resolve the global ferry dump (cached -> vendored snapshot -> live sweep).

    ``--force`` runs a fresh live Overpass sweep (slow; network required).
    """
    typer.echo(f"retrieved global ferries -> {fetch_ferries(force=force)}")


@app.command()
def all(force: bool = _FORCE) -> None:  # noqa: A001 (CLI verb)
    """Retrieve every source: OpenFlights, GeoNames, OSM ferries."""
    fetch_openflights(force=force)
    fetch_geonames(force=force)
    fetch_ferries(force=force)
    typer.echo("retrieved all sources")

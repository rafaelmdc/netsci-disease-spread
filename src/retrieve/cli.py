"""`netsci retrieve ...` — fetch raw source data."""

from __future__ import annotations

import typer

from src.retrieve.geonames import fetch as fetch_geonames
from src.retrieve.openflights import fetch as fetch_openflights
from src.retrieve.osm_ferries import fetch as fetch_ferries

app = typer.Typer(help="Module 1: data retrieval.")


@app.command()
def openflights() -> None:
    """Download OpenFlights airports + routes (the air layer)."""
    typer.echo(f"retrieved OpenFlights -> {fetch_openflights()}")


@app.command()
def geonames() -> None:
    """Download GeoNames cities1000 (the canonical city node set)."""
    typer.echo(f"retrieved GeoNames cities -> {fetch_geonames()}")


@app.command()
def ferries() -> None:
    """Build the global OSM ferry dump (one-time; cached as ferries_world.json)."""
    typer.echo(f"retrieved global ferries -> {fetch_ferries()}")


@app.command()
def all() -> None:  # noqa: A001 (CLI verb)
    """Retrieve every source: OpenFlights, GeoNames, OSM ferries."""
    fetch_openflights()
    fetch_geonames()
    fetch_ferries()
    typer.echo("retrieved all sources")

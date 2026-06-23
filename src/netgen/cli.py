"""`netsci netgen ...` — build standardized networks."""

from __future__ import annotations

import typer

from src.config import NetworkConfig
from src.netgen.graph_io import write_graphml
from src.netgen.toy import build_toy_graph
from src.paths import combo_name, processed_graph

app = typer.Typer(help="Module 2: network generation.")


@app.command()
def toy(region: str = "toy") -> None:
    """Write the tiny synthetic mini-Europe air network (for the skeleton)."""
    cfg = NetworkConfig(region=region)
    graph = build_toy_graph(cfg)
    out = processed_graph(region, combo_name(["air"]))
    write_graphml(graph, out)
    typer.echo(f"wrote {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges -> {out}")


@app.command()
def build(
    region: str = "europe",
    layers: str = typer.Option("air", help="comma-separated layers: air,land,water"),
) -> None:
    """Build a real network for a region/layers (implemented in Slice 1+)."""
    raise typer.Exit(
        typer.echo(
            f"netgen build({region=}, {layers=}) not implemented yet — "
            "use `netgen toy` for the walking skeleton. See docs/ROADMAP.md."
        )
    )

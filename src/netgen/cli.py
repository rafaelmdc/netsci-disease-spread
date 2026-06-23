"""`netsci netgen ...` — build standardized networks."""

from __future__ import annotations

import typer

from src.config import Layer, NetworkConfig
from src.netgen.build import build_network
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
    """Build a real network from retrieved data for a region and layer set."""
    layer_list = [Layer(x.strip()) for x in layers.split(",") if x.strip()]
    cfg = NetworkConfig(region=region, layers=layer_list)
    graph = build_network(cfg)
    out = processed_graph(region, combo_name([layer.value for layer in layer_list]))
    write_graphml(graph, out)
    typer.echo(
        f"{region}/{combo_name([layer.value for layer in layer_list])}: "
        f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges -> {out}"
    )

"""Per-layer network builders, via a registry.

A layer builder is ``(region) -> nx.DiGraph`` returning a directed graph
whose edges are tagged ``layer=<name>`` with a ``raw_weight`` frequency and
a ``weight`` used by diffusion. ``netgen.build`` composes the requested
layers onto a shared node set. Adding land/water (Slice 4) is one more
registered builder; nothing else changes.
"""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import pandas as pd

from src.config import Layer
from src.netgen.regions import in_region
from src.paths import raw_dir
from src.registry import Registry

LayerBuilder = Callable[[str], nx.DiGraph]
LAYER_REGISTRY: Registry[Layer, LayerBuilder] = Registry("layer")

_AIRPORT_COLS = [
    "airport_id", "name", "city", "country", "iata", "icao",
    "lat", "lon", "alt", "tz_offset", "dst", "tz", "type", "source",
]
_ROUTE_COLS = [
    "airline", "airline_id", "src", "src_id",
    "dst", "dst_id", "codeshare", "stops", "equipment",
]


@LAYER_REGISTRY.register(Layer.AIR)
def build_air_layer(region: str) -> nx.DiGraph:
    """Air layer from OpenFlights: airports in `region` + direct routes between them."""
    air = raw_dir("air")
    airports = pd.read_csv(
        air / "airports.dat", header=None, names=_AIRPORT_COLS, na_values="\\N"
    )
    routes = pd.read_csv(
        air / "routes.dat", header=None, names=_ROUTE_COLS, na_values="\\N"
    )

    airports = airports[airports["iata"].notna()].copy()
    airports = airports[airports["tz"].map(lambda tz: in_region(tz, region))]
    airports = airports.drop_duplicates(subset="iata", keep="first")
    region_iatas = set(airports["iata"])

    # direct flights (stops == 0) between two in-region airports
    routes = routes[(routes["stops"] == 0)]
    routes = routes[routes["src"].isin(region_iatas) & routes["dst"].isin(region_iatas)]
    edges = routes.groupby(["src", "dst"]).size().reset_index(name="raw_weight")

    graph = nx.DiGraph()
    attrs = airports.set_index("iata")
    used = set(edges["src"]) | set(edges["dst"])
    for iata in used:
        row = attrs.loc[iata]
        graph.add_node(
            iata,
            name=str(row["name"]),
            city=str(row["city"]),
            country=str(row["country"]),
            region=region,
            lat=float(row["lat"]),
            lon=float(row["lon"]),
        )
    for src, dst, w in edges.itertuples(index=False):
        graph.add_edge(src, dst, layer=Layer.AIR.value, raw_weight=float(w), weight=float(w))
    return graph

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
import numpy as np
import pandas as pd

from src.config import Layer, NetworkConfig
from src.netgen.flows import radiation_flows, top_k_edges
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


@LAYER_REGISTRY.register(Layer.LAND)
def build_land_layer(region: str, k: int = 8) -> nx.DiGraph:
    """Ground-mobility layer over the same city node set, with flow weights from
    the radiation model (Simini et al.) — applied uniformly to every region.

    NOTE (gap to close in iteration): topology here reuses the air node set and
    radiation-estimated flows, NOT real OSM/GRIP rail/road geometry, and is not
    yet validated against Eurostat. Those refinements are tracked in ROADMAP.
    """
    air = build_air_layer(region)
    nodes = list(air.nodes())
    defaults = NetworkConfig()
    pop = np.array([defaults.p0 + air.degree(n) * defaults.p_route for n in nodes], dtype=float)
    lat = np.array([air.nodes[n]["lat"] for n in nodes])
    lon = np.array([air.nodes[n]["lon"] for n in nodes])

    flux = radiation_flows(pop, lat, lon)
    edges = top_k_edges(flux, k)

    # scale land weights to the air layer's max so the two are comparable when
    # overlaid under one travel rate (per-layer travel rates: future work)
    air_max = max((d["weight"] for *_, d in air.edges(data=True)), default=1.0)
    flux_max = max((w for *_, w in edges), default=1.0)

    graph = nx.DiGraph()
    for node, data in air.nodes(data=True):
        graph.add_node(node, **data)
    for i, j, w in edges:
        graph.add_edge(
            nodes[i], nodes[j],
            layer=Layer.LAND.value,
            raw_weight=w,
            weight=w / flux_max * air_max,
        )
    return graph

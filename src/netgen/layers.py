"""Per-layer network builders, all on the shared GeoNames *city* node set.

A layer builder is ``(region) -> nx.DiGraph`` whose nodes are city ids and
whose edges are tagged ``layer=<name>`` with a ``raw_weight`` and a ``weight``
used by diffusion. Airports and ferry terminals are snapped to their nearest
city, so air, land and water overlay on the same real cities (with real
populations). ``netgen.build`` composes the requested layers.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import networkx as nx
import numpy as np
import pandas as pd

from src.config import Layer
from src.netgen.flows import radiation_flows, top_k_edges
from src.netgen.places import region_cities, resolve_served_cities, snap
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

_LAND_TOP_N = 1000  # cap land node set to the N most populous cities (tractability)


def _add_city_nodes(
    graph: nx.DiGraph, city_ids: set[str], cities: pd.DataFrame, region: str
) -> None:
    attrs = cities.set_index("city_id")
    for cid in city_ids:
        row = attrs.loc[cid]
        graph.add_node(
            cid,
            name=str(row["name"]),
            country=str(row["country"]),
            region=region,
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            population=int(row["population"]),
        )


@LAYER_REGISTRY.register(Layer.AIR)
def build_air_layer(region: str) -> nx.DiGraph:
    """Air layer: OpenFlights routes aggregated to the cities their airports serve.

    Each airport is assigned to its city via OpenFlights' curated ``city`` label
    (resolved to a GeoNames node), with a gravity-catchment fallback to the
    nearest real city within the basin — see :func:`resolve_served_cities`. This
    is what makes all five London airports collapse onto the single London node.

    Every node is therefore a **real GeoNames place with a real population**.
    Airports whose served place has no real city within the catchment basin
    (remote islands below GeoNames' floor) are *dropped*, not given a proxy
    population: a fabricated population would silently drive the epidemic
    dynamics. This loses ~0–5% of regional air *traffic* (most in Oceania) — a
    documented, conservative bias. See docs/DATA.md and scripts/validate_snap.py.
    """
    cities = region_cities(region)
    air = raw_dir("air")
    airports = pd.read_csv(air / "airports.dat", header=None, names=_AIRPORT_COLS, na_values="\\N")
    airports = airports[
        airports["iata"].notna() & airports["tz"].map(lambda t: in_region(t, region))
    ]

    city_of = resolve_served_cities(
        airports["city"].tolist(),
        airports["lat"].to_numpy(),
        airports["lon"].to_numpy(),
        cities,
    )
    iata_to_city = {
        iata: cid for iata, cid in zip(airports["iata"], city_of, strict=True) if cid is not None
    }

    routes = pd.read_csv(air / "routes.dat", header=None, names=_ROUTE_COLS, na_values="\\N")
    routes = routes[routes["stops"] == 0]
    routes["src_city"] = routes["src"].map(iata_to_city)
    routes["dst_city"] = routes["dst"].map(iata_to_city)
    routes = routes.dropna(subset=["src_city", "dst_city"])
    routes = routes[routes["src_city"] != routes["dst_city"]]
    edges = routes.groupby(["src_city", "dst_city"]).size().reset_index(name="w")

    graph = nx.DiGraph()
    used = set(edges["src_city"]) | set(edges["dst_city"])
    _add_city_nodes(graph, used, cities, region)
    for src, dst, w in edges.itertuples(index=False):
        graph.add_edge(src, dst, layer=Layer.AIR.value, raw_weight=float(w), weight=float(w))
    return graph


@LAYER_REGISTRY.register(Layer.LAND)
def build_land_layer(region: str, k: int = 8) -> nx.DiGraph:
    """Ground-mobility layer (aggregated multilayer metapopulation, GLEAM/Balcan).

    Edge weight is the radiation-model *per-capita* commuting kernel
    K_ij = flux_ij / pop_i (Simini 2012): the fraction of city i's residents
    whose nearest opportunity-weighted destination is j. The engine multiplies
    it by the land travel rate (a commuting fraction), so no arbitrary
    rescaling is needed. Real GeoNames populations, capped to the top-N cities.
    GAP: not yet validated against Eurostat; OSM/GRIP geometry TBD.
    """
    cities = region_cities(region, top_n=_LAND_TOP_N)
    pop = cities["population"].to_numpy(dtype=float)
    lat = cities["lat"].to_numpy()
    lon = cities["lon"].to_numpy()
    ids = cities["city_id"].to_numpy()

    flux = radiation_flows(pop, lat, lon)
    with np.errstate(divide="ignore", invalid="ignore"):
        kernel = np.where(pop[:, None] > 0, flux / pop[:, None], 0.0)  # per-capita K_ij
    edges = top_k_edges(kernel, k)

    graph = nx.DiGraph()
    _add_city_nodes(graph, set(ids), cities, region)
    for i, j, w in edges:
        graph.add_edge(ids[i], ids[j], layer=Layer.LAND.value, raw_weight=w, weight=w)
    return graph


@LAYER_REGISTRY.register(Layer.WATER)
def build_water_layer(region: str) -> nx.DiGraph:
    """Sea/ferry layer from the real OSM global ferry dump, snapped to cities.

    Edge weight is ferry-route frequency between the two cities (a passenger-
    volume proxy, like air; OSM has no passenger counts). The engine multiplies
    it by the water travel rate.
    """
    path = raw_dir("water") / "ferries_world.json"
    routes = json.loads(path.read_text()) if path.exists() else []
    cities = region_cities(region)

    pts_lat, pts_lon = [], []
    for r in routes:
        pts_lat += [r["a"][0], r["b"][0]]
        pts_lon += [r["a"][1], r["b"][1]]
    snapped = snap(np.array(pts_lat), np.array(pts_lon), cities) if routes else []

    # ferries are bidirectional services: count per unordered city pair
    pair_counts: dict[tuple[str, str], int] = {}
    for idx in range(len(routes)):
        a, b = snapped[2 * idx], snapped[2 * idx + 1]
        if a and b and a != b:
            key = (a, b) if a < b else (b, a)
            pair_counts[key] = pair_counts.get(key, 0) + 1

    graph = nx.DiGraph()
    _add_city_nodes(graph, {c for pair in pair_counts for c in pair}, cities, region)
    for (a, b), w in pair_counts.items():
        graph.add_edge(a, b, layer=Layer.WATER.value, raw_weight=float(w), weight=float(w))
        graph.add_edge(b, a, layer=Layer.WATER.value, raw_weight=float(w), weight=float(w))
    return graph

"""A tiny synthetic 'mini-Europe' air network for the walking skeleton and
tests. Deterministic; has two clear hubs so centralities are non-trivial.
"""

from __future__ import annotations

import networkx as nx

from src.config import NetworkConfig

# (id, name, lat, lon) — loosely geographic so the geo viz looks sensible.
_CITIES = [
    ("LON", "London", 51.5, -0.1),
    ("PAR", "Paris", 48.9, 2.4),
    ("FRA", "Frankfurt", 50.0, 8.6),
    ("AMS", "Amsterdam", 52.3, 4.8),
    ("MAD", "Madrid", 40.4, -3.7),
    ("ROM", "Rome", 41.9, 12.5),
    ("BER", "Berlin", 52.5, 13.4),
    ("LIS", "Lisbon", 38.7, -9.1),
    ("WAW", "Warsaw", 52.2, 21.0),
    ("ATH", "Athens", 38.0, 23.7),
    ("OSL", "Oslo", 59.9, 10.8),
    ("DUB", "Dublin", 53.3, -6.3),
]

# Directed routes with a frequency proxy (raw_weight). LON and FRA are hubs.
_ROUTES = [
    ("LON", "PAR", 9), ("LON", "FRA", 8), ("LON", "AMS", 7), ("LON", "MAD", 6),
    ("LON", "DUB", 8), ("LON", "ROM", 5), ("LON", "BER", 5),
    ("FRA", "PAR", 7), ("FRA", "AMS", 6), ("FRA", "BER", 6), ("FRA", "WAW", 5),
    ("FRA", "ROM", 5), ("FRA", "ATH", 4), ("FRA", "OSL", 4),
    ("PAR", "MAD", 5), ("PAR", "ROM", 5), ("PAR", "LIS", 4),
    ("MAD", "LIS", 6), ("AMS", "OSL", 4), ("BER", "WAW", 5), ("ROM", "ATH", 5),
]


def build_toy_graph(cfg: NetworkConfig | None = None) -> nx.DiGraph:
    cfg = cfg or NetworkConfig()
    g = nx.DiGraph()
    for node_id, name, lat, lon in _CITIES:
        g.add_node(
            node_id, name=name, city=name, country="EU",
            region=cfg.region, lat=lat, lon=lon,
        )
    for src, dst, freq in _ROUTES:
        # symmetric routes; weight normalised by frequency for travel rate
        for a, b in ((src, dst), (dst, src)):
            g.add_edge(a, b, layer="air", raw_weight=float(freq), weight=float(freq))

    # population proxy: pop(v) = p0 + degree(v) * p_route
    for node, deg in g.degree():
        g.nodes[node]["population"] = int(cfg.p0 + deg * cfg.p_route)
    return g

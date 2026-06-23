"""GraphML read/write — the canonical, portable network format.

GraphML is Gephi-readable and preserves typed node/edge attributes. Nodes
carry ``name, city, country, region, lat, lon, population``; edges carry
``layer, weight, raw_weight``.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from src.paths import ensure_parent


def write_graphml(graph: nx.DiGraph, path: str | Path) -> Path:
    path = Path(path)
    ensure_parent(path)
    nx.write_graphml(graph, path)
    return path


def read_graphml(path: str | Path) -> nx.DiGraph:
    # node_type=str keeps ids stable; networkx restores typed attributes.
    return nx.read_graphml(path, node_type=str, force_multigraph=False)

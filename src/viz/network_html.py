"""Interactive network view as standalone HTML (pyvis / vis.js)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

from src.paths import ensure_parent


def network_to_html(graph: nx.DiGraph, path: str | Path, targets: list[str] | None = None) -> Path:
    """Write an interactive HTML network. Node size ~ degree; vaccinated
    targets highlighted."""
    path = Path(path)
    ensure_parent(path)
    targets = set(targets or [])

    net = Network(height="750px", width="100%", directed=True, cdn_resources="in_line")
    degrees = dict(graph.degree())
    max_deg = max(degrees.values()) if degrees else 1

    for node, data in graph.nodes(data=True):
        deg = degrees.get(node, 0)
        net.add_node(
            node,
            label=str(data.get("name", node)),
            value=deg,
            color="#d62728" if node in targets else "#1f77b4",
            title=f"{data.get('name', node)} | degree={deg} | pop={data.get('population', '?')}",
            size=10 + 30 * deg / max_deg,
        )
    for u, v, data in graph.edges(data=True):
        net.add_edge(u, v, value=float(data.get("weight", 1.0)))

    net.save_graph(str(path))
    return path

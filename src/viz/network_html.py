"""Interactive network view as standalone HTML (pyvis / vis.js).

Nodes are placed at their geographic coordinates with physics **disabled**.
This avoids the browser running a force-directed layout over hundreds of
nodes and thousands of edges (which shows an endless "loading" bar), and it
makes the picture an actual map: hubs sit where the cities are.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

from src.paths import ensure_parent

# screen-pixel scale for lon/lat; y is negated because screen y grows downward
_GEO_SCALE = 40.0


def network_to_html(graph: nx.DiGraph, path: str | Path, targets: list[str] | None = None) -> Path:
    """Write an interactive HTML network on a geographic layout (physics off).
    Node size ~ degree; vaccinated targets highlighted in red."""
    path = Path(path)
    ensure_parent(path)
    targets = set(targets or [])

    # 100vh so the canvas fills the whole window (pyvis defaults to a short,
    # fixed-height bordered box that only covers the top of the page).
    net = Network(height="100vh", width="100%", directed=True, cdn_resources="in_line")
    net.toggle_physics(False)  # fixed geographic positions -> no stabilization wait

    degrees = dict(graph.degree())
    max_deg = max(degrees.values()) if degrees else 1

    for node, data in graph.nodes(data=True):
        deg = degrees.get(node, 0)
        lon = float(data.get("lon", 0.0))
        lat = float(data.get("lat", 0.0))
        net.add_node(
            node,
            label=str(data.get("name", node)),
            x=lon * _GEO_SCALE,
            y=-lat * _GEO_SCALE,
            physics=False,
            color="#d62728" if node in targets else "#1f77b4",
            title=f"{data.get('name', node)} | degree={deg} | pop={data.get('population', '?')}",
            size=8 + 32 * deg / max_deg,
        )
    for u, v, data in graph.edges(data=True):
        net.add_edge(u, v, value=float(data.get("weight", 1.0)), color="#cccccc")

    net.save_graph(str(path))
    return path

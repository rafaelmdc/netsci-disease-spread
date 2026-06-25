"""Export networks for Gephi (.gexf).

Two flavours, both written next to the run/network they describe:

* ``network_gexf`` — *static* topology: nodes carry name, lat/lon, population,
  degree and betweenness; edges carry their layer and weight. A ``viz``
  position (lon, lat) opens Gephi on a map-like layout. Use this for structural
  work (layout, modularity, centrality colouring).

* ``run_gexf`` — *dynamic* outbreak: the same topology, plus each node's
  per-day ``infectious`` count as a **dynamic attribute**. Gephi's Timeline
  (bottom of the window) plays the outbreak through time — colour/size the
  nodes by ``infectious`` to animate the spread. This is the per-node history
  from ``node_timeseries.parquet`` (columns: day, node, name, lat, lon,
  infectious) rendered for the desktop tool instead of the browser.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from src.evaluate.centrality import betweenness
from src.paths import ensure_parent

_LAYERS = ("air", "land", "water")


def _edge_layer(data: dict) -> str:
    """The dominant layer of an edge, from its per-layer weights (w_air/...)."""
    present = [layer for layer in _LAYERS if float(data.get(f"w_{layer}", 0.0)) > 0]
    if len(present) == 1:
        return present[0]
    if present:  # multi-layer edge: name the heaviest
        return max(present, key=lambda layer: float(data.get(f"w_{layer}", 0.0)))
    return str(data.get("layer", "air"))


def _clean_topology(graph: nx.DiGraph) -> nx.DiGraph:
    """A fresh DiGraph with only GEXF-safe, Gephi-useful attributes."""
    btw = betweenness(graph)  # cached on the graph; keyed by node id
    deg = dict(graph.degree())
    out = nx.DiGraph()
    for node, data in graph.nodes(data=True):
        lon, lat = float(data.get("lon", 0.0)), float(data.get("lat", 0.0))
        out.add_node(
            node,
            name=str(data.get("name", node)),
            lat=lat,
            lon=lon,
            population=float(data.get("population", 0.0)),
            degree=int(deg.get(node, 0)),
            betweenness=float(btw.get(node, 0.0)),
            # Gephi opens on a geographic layout (x=lon, y=lat).
            viz={"position": {"x": lon, "y": lat, "z": 0.0}},
        )
    for u, v, data in graph.edges(data=True):
        out.add_edge(u, v, layer=_edge_layer(data), weight=float(data.get("weight", 1.0)))
    return out


def network_gexf(graph: nx.DiGraph, path: str | Path) -> Path:
    """Write the static network topology for Gephi."""
    path = Path(path)
    ensure_parent(path)
    nx.write_gexf(_clean_topology(graph), str(path))
    return path


def run_gexf(graph: nx.DiGraph, node_ts: pd.DataFrame, path: str | Path) -> Path:
    """Write the dynamic outbreak (per-node ``infectious`` over time) for Gephi's
    Timeline. ``node_ts`` is the tidy per-node table (day, node, infectious)."""
    path = Path(path)
    ensure_parent(path)
    out = _clean_topology(graph)
    out.graph["mode"] = "dynamic"
    out.graph["timeformat"] = "integer"
    last = int(node_ts["day"].max()) + 1
    for node, sub in node_ts.groupby("node"):
        if node not in out:
            continue
        # Dynamic attribute: list of (value, start, end) spells, one per day.
        spells = [
            (int(v), int(d), int(d) + 1)
            for d, v in zip(sub["day"], sub["infectious"], strict=True)
        ]
        out.nodes[node]["infectious"] = spells
        # Make the node itself live across the whole run so Gephi keeps it on
        # screen for the full timeline (not only on days it carries infection).
        out.nodes[node]["spells"] = [(0, last)]
    nx.write_gexf(out, str(path))
    return path

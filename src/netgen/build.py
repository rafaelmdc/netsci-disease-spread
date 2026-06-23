"""Compose the requested layers into one network and assign populations.

For a single layer (air, the Slice 1 MVP) this is just that layer. For
multiple layers, edges are overlaid on the shared node set; a same-endpoint
edge present in several layers accumulates ``weight`` and records the set of
contributing layers. (City-level node canonicalization for true multimodal
overlay lands in Slice 4.)
"""

from __future__ import annotations

import networkx as nx

from src.config import NetworkConfig
from src.netgen.layers import LAYER_REGISTRY


def build_network(cfg: NetworkConfig) -> nx.DiGraph:
    combined = nx.DiGraph()
    for layer in cfg.layers:
        sub = LAYER_REGISTRY.get(layer)(cfg.region)
        for node, data in sub.nodes(data=True):
            if node not in combined:
                combined.add_node(node, **data)
        for u, v, data in sub.edges(data=True):
            if combined.has_edge(u, v):
                combined[u][v]["weight"] += data["weight"]
                combined[u][v]["raw_weight"] += data["raw_weight"]
                combined[u][v]["layer"] = f"{combined[u][v]['layer']},{data['layer']}"
            else:
                combined.add_edge(u, v, **data)

    # population proxy: pop(v) = p0 + degree(v) * p_route
    for node, deg in combined.degree():
        combined.nodes[node]["population"] = int(cfg.p0 + deg * cfg.p_route)
    return combined

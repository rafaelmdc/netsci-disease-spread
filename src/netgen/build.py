"""Compose the requested layers into one network and assign populations.

Each edge keeps a *per-layer* weight (``w_air``, ``w_land``, ``w_water``) as
well as a combined ``weight`` (their sum, used for visualisation and as the
fallback when no per-layer travel rates are given). Keeping the layers
separable is what lets the engine apply a distinct travel rate per layer.
"""

from __future__ import annotations

import networkx as nx

from src.config import NetworkConfig
from src.netgen.layers import LAYER_REGISTRY


# per-layer weight attribute name, e.g. air -> "w_air"
def layer_weight_key(layer: str) -> str:
    return f"w_{layer}"


def build_network(cfg: NetworkConfig) -> nx.DiGraph:
    combined = nx.DiGraph()
    for layer in cfg.layers:
        sub = LAYER_REGISTRY.get(layer)(cfg.region)
        wkey = layer_weight_key(layer.value)
        for node, data in sub.nodes(data=True):
            if node not in combined:
                combined.add_node(node, **data)
        for u, v, data in sub.edges(data=True):
            w = float(data["weight"])
            if combined.has_edge(u, v):
                e = combined[u][v]
                e["weight"] += w
                e[wkey] = e.get(wkey, 0.0) + w
                e["layer"] = f"{e['layer']},{layer.value}"
            else:
                combined.add_edge(u, v, layer=layer.value, weight=w, **{wkey: w})

    # zero-fill missing per-layer weights so every edge has all keys (GraphML)
    keys = [layer_weight_key(layer.value) for layer in cfg.layers]
    for _, _, data in combined.edges(data=True):
        for k in keys:
            data.setdefault(k, 0.0)

    # population proxy: pop(v) = p0 + degree(v) * p_route
    for node, deg in combined.degree():
        combined.nodes[node]["population"] = int(cfg.p0 + deg * cfg.p_route)
    return combined

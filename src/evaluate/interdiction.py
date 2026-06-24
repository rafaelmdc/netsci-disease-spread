"""Air-interdiction experiment: the result only the multilayer can produce.

Vaccination removes *nodes* (immunise a city). Interdiction removes *edges*
(close flight routes) while the cities stay alive on roads and ferries — so it
asks a different question: can you stop the outbreak by grounding flights, or do
land and water carry it anyway?

Edges carry per-layer weights (``w_air`` / ``w_water`` / ``w_land``), so closing
a layer is a graph transform; the engine then runs unchanged on the result. See
docs/EXPERIMENTS.md §4 for the A–D scenarios.
"""

from __future__ import annotations

import networkx as nx

from src.config import RunConfig
from src.evaluate.centrality import betweenness
from src.evaluate.engine import simulate

_LAYER_KEYS = ("w_air", "w_water", "w_land")


def _dead(data: dict) -> bool:
    """A layered edge with every per-layer weight now zero carries no one."""
    return all(float(data.get(k, 0.0)) == 0.0 for k in _LAYER_KEYS)


def close_layer(graph: nx.DiGraph, layer: str) -> nx.DiGraph:
    """Copy of the graph with one transport layer shut down.

    Layered edges get that layer's weight zeroed (and are dropped if nothing is
    left); plain air-only graphs (generic ``weight``, no per-layer keys) have
    their edges removed when ``layer == 'air'``."""
    g = graph.copy()
    wkey = f"w_{layer}"
    remove = []
    for u, v, d in g.edges(data=True):
        if any(k in d for k in _LAYER_KEYS):
            d[wkey] = 0.0
            if _dead(d):
                remove.append((u, v))
        elif layer == "air":  # generic edge == an air route
            remove.append((u, v))
    g.remove_edges_from(remove)
    return g


def close_airports(graph: nx.DiGraph, airports: list[str]) -> nx.DiGraph:
    """Copy with flights to/from the given airports stopped (their air weight
    zeroed), but their land/ferry links kept."""
    g = graph.copy()
    aset = set(airports)
    remove = []
    for u, v, d in g.edges(data=True):
        if u not in aset and v not in aset:
            continue
        if any(k in d for k in _LAYER_KEYS):
            d["w_air"] = 0.0
            if _dead(d):
                remove.append((u, v))
        else:
            remove.append((u, v))
    g.remove_edges_from(remove)
    return g


def _top_k(scores: dict[str, float], k: int) -> list[str]:
    return sorted(scores, key=lambda n: scores[n], reverse=True)[:k]


def scenarios(graph: nx.DiGraph, k: int = 10) -> dict[str, nx.DiGraph]:
    """The A–D interdiction scenarios as transformed graphs."""
    air_only = close_layer(close_layer(graph, "land"), "water")
    degree_scores = dict(graph.degree())
    return {
        "A · full network": graph,
        "B · air closed, land+water open": close_layer(graph, "air"),
        "C · air closed (air-only model)": close_layer(air_only, "air"),
        f"D1 · top-{k} airports by degree closed": close_airports(graph, _top_k(degree_scores, k)),
        f"D2 · top-{k} airports by betweenness closed": close_airports(
            graph, _top_k(betweenness(graph), k)
        ),
    }


def run_scenarios(graph: nx.DiGraph, cfg: RunConfig, k: int = 10) -> dict[str, dict]:
    """Run every scenario under one config; return active-infection curves and
    summaries keyed by scenario name."""
    out: dict[str, dict] = {}
    for name, g in scenarios(graph, k).items():
        res = simulate(g, cfg)
        infectious = res.timeseries.get("I", next(iter(res.timeseries.values())))
        out[name] = {"infectious": list(infectious), "summary": res.summary}
    return out

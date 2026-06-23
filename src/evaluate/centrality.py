"""Centrality computations, cached per graph object.

Betweenness is the expensive step and is identical across every run on a
given network (it depends only on topology). A sweep runs the same graph
dozens of times, so we memoise it per graph object — computed once per
process, reused by both the betweenness strategy and the structural metric.
"""

from __future__ import annotations

from weakref import WeakKeyDictionary

import networkx as nx

_betweenness_cache: WeakKeyDictionary[nx.Graph, dict[str, float]] = WeakKeyDictionary()


def betweenness(graph: nx.DiGraph) -> dict[str, float]:
    """Unweighted (topological) betweenness centrality, cached per graph.

    Edge ``weight`` is flight frequency, not a distance, so it is deliberately
    NOT passed to ``betweenness_centrality``.
    """
    cached = _betweenness_cache.get(graph)
    if cached is None:
        cached = nx.betweenness_centrality(graph)
        _betweenness_cache[graph] = cached
    return cached

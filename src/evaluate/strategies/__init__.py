"""Vaccination target selection.

Every strategy has the same signature ``select(graph, cfg, rng) -> list[node]``,
so adding one is a single function. Slice 0 ships control/random/degree/
betweenness; kcore/subgraph follow in Slice 3.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from src.config import StrategyConfig, StrategyName


def select_targets(graph: nx.DiGraph, cfg: StrategyConfig, rng: np.random.Generator) -> list[str]:
    nodes = list(graph.nodes())
    budget = min(cfg.budget, len(nodes))

    if cfg.name is StrategyName.CONTROL or budget == 0:
        return []
    if cfg.name is StrategyName.RANDOM:
        return [nodes[i] for i in rng.choice(len(nodes), size=budget, replace=False)]
    if cfg.name is StrategyName.DEGREE:
        ranked = sorted(nodes, key=lambda n: graph.degree(n), reverse=True)
        return ranked[:budget]
    if cfg.name is StrategyName.BETWEENNESS:
        bc = nx.betweenness_centrality(graph, weight="weight")
        ranked = sorted(nodes, key=lambda n: bc[n], reverse=True)
        return ranked[:budget]

    raise NotImplementedError(
        f"strategy {cfg.name.value!r} not implemented yet (Slice 3)."
    )

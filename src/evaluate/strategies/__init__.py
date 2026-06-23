"""Vaccination target selection, via a strategy registry.

Each strategy is a function ``(graph, budget, rng) -> list[node]`` registered
under its name, so adding one is a single decorated function. ``select_targets``
resolves the configured strategy. Slice 0/1 ship control/random/degree/
betweenness; kcore/subgraph follow in Slice 3.
"""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import numpy as np

from src.config import StrategyConfig, StrategyName
from src.registry import Registry

Selector = Callable[[nx.DiGraph, int, np.random.Generator], list[str]]
STRATEGY_REGISTRY: Registry[StrategyName, Selector] = Registry("strategy")


@STRATEGY_REGISTRY.register(StrategyName.CONTROL)
def _control(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    return []


@STRATEGY_REGISTRY.register(StrategyName.RANDOM)
def _random(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    nodes = list(graph.nodes())
    return [nodes[i] for i in rng.choice(len(nodes), size=budget, replace=False)]


@STRATEGY_REGISTRY.register(StrategyName.DEGREE)
def _degree(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    return [n for n, _ in sorted(graph.degree(), key=lambda kv: kv[1], reverse=True)[:budget]]


@STRATEGY_REGISTRY.register(StrategyName.BETWEENNESS)
def _betweenness(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    # Topological (unweighted) betweenness: edge `weight` is flight *frequency*,
    # not a distance, so it must NOT be passed to betweenness (which minimises
    # summed weight). This matches the structural-bridge / Guimera framing.
    bc = nx.betweenness_centrality(graph)
    return [n for n, _ in sorted(bc.items(), key=lambda kv: kv[1], reverse=True)[:budget]]


def select_targets(graph: nx.DiGraph, cfg: StrategyConfig, rng: np.random.Generator) -> list[str]:
    budget = min(cfg.budget, graph.number_of_nodes())
    if cfg.name is StrategyName.CONTROL or budget == 0:
        return []
    return STRATEGY_REGISTRY.get(cfg.name)(graph, budget, rng)

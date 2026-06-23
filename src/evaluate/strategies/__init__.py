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
from src.evaluate.centrality import betweenness
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
    # topological betweenness, cached per graph (see centrality.py)
    bc = betweenness(graph)
    return [n for n, _ in sorted(bc.items(), key=lambda kv: kv[1], reverse=True)[:budget]]


@STRATEGY_REGISTRY.register(StrategyName.KCORE)
def _kcore(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    # innermost k-shell first: the network core where the best spreaders sit
    # (Kitsak et al.). Computed on the undirected projection.
    core = nx.core_number(nx.DiGraph(graph).to_undirected())
    return [n for n, _ in sorted(core.items(), key=lambda kv: kv[1], reverse=True)[:budget]]


@STRATEGY_REGISTRY.register(StrategyName.SUBGRAPH)
def _subgraph(graph: nx.DiGraph, budget: int, rng: np.random.Generator) -> list[str]:
    # dense-motif proxy: triangle participation (cities embedded in tightly
    # interconnected clusters). A full graphlet (ORCA) score is future work.
    tri = nx.triangles(nx.DiGraph(graph).to_undirected())
    return [n for n, _ in sorted(tri.items(), key=lambda kv: kv[1], reverse=True)[:budget]]


def select_targets(graph: nx.DiGraph, cfg: StrategyConfig, rng: np.random.Generator) -> list[str]:
    budget = min(cfg.budget, graph.number_of_nodes())
    if cfg.name is StrategyName.CONTROL or budget == 0:
        return []
    return STRATEGY_REGISTRY.get(cfg.name)(graph, budget, rng)

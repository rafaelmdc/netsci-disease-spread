"""Tests for the modern targeting strategies (Collective Influence,
non-backtracking) and the non-backtracking epidemic-threshold verification.

Toy graphs with analytically known answers keep these fast and deterministic
(RESEARCH-ROADMAP #2 and #3). Not yet run against the full networks — that
happens when they are added to the sweep.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from src.config import StrategyConfig, StrategyName
from src.evaluate.centrality import (
    collective_influence,
    nb_leading_eigenvalue,
    nonbacktracking_scores,
)
from src.evaluate.strategies import STRATEGY_REGISTRY, select_targets


def _rng() -> np.random.Generator:
    return np.random.default_rng(0)


def test_new_strategies_registered():
    assert StrategyName.COLLECTIVE_INFLUENCE in STRATEGY_REGISTRY
    assert StrategyName.NONBACKTRACKING in STRATEGY_REGISTRY


@pytest.mark.parametrize(
    "name", [StrategyName.COLLECTIVE_INFLUENCE, StrategyName.NONBACKTRACKING]
)
def test_selects_exactly_budget_distinct_nodes(name):
    g = nx.karate_club_graph().to_directed()
    cfg = StrategyConfig(name=name, budget=5)
    picks = select_targets(g, cfg, _rng())
    assert len(picks) == 5
    assert len(set(picks)) == 5
    assert set(picks) <= set(g.nodes())


def test_nb_eigenvalue_regular_graphs():
    # A k-regular graph has non-backtracking leading eigenvalue k-1.
    k4 = nx.complete_graph(4).to_directed()  # 3-regular
    assert nb_leading_eigenvalue(k4) == pytest.approx(2.0, abs=1e-6)
    # A cycle is 2-regular: the Hashimoto operator is a permutation, |lambda|=1.
    c6 = nx.cycle_graph(6).to_directed()
    assert nb_leading_eigenvalue(c6) == pytest.approx(1.0, abs=1e-6)


def test_ci_scores_every_node_and_rewards_a_bridge():
    # two triangles joined by one bridge edge (0--3): node 0 has the same degree
    # as its triangle-mates but reaches the far triangle, so its radius-2 CI is
    # strictly larger than a purely internal triangle node's.
    g = nx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3)])
    ci = collective_influence(g, radius=2)
    assert set(ci) == set(g.nodes())
    assert ci[0] > ci[1]  # the bridge endpoint outranks an internal node


def test_nb_scores_present_for_all_nodes():
    g = nx.karate_club_graph().to_directed()
    scores = nonbacktracking_scores(g)
    assert set(scores) == set(g.nodes())
    assert all(v >= 0.0 for v in scores.values())


def test_ci_cache_returns_same_object():
    g = nx.karate_club_graph().to_directed()
    assert collective_influence(g, radius=2) is collective_influence(g, radius=2)

import networkx as nx

from src.config import (
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    StrategyConfig,
    StrategyName,
)
from src.evaluate.engine import simulate
from src.evaluate.metrics import characterize, degree_betweenness
from src.evaluate.strategies import select_targets
from src.netgen.toy import build_toy_graph


def _run(strategy):
    return RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.32, gamma=0.12)),
        strategy=strategy,
        sim={"horizon": 30, "seed": 0},
    )


def test_toy_graph_shape():
    g = build_toy_graph()
    assert g.number_of_nodes() == 12
    assert nx.is_weakly_connected(g)
    assert all("population" in g.nodes[n] for n in g.nodes)


def test_betweenness_targets_are_hubs():
    g = build_toy_graph()
    import numpy as np

    targets = select_targets(
        g, StrategyConfig(name=StrategyName.BETWEENNESS, budget=4), np.random.default_rng(0)
    )
    assert len(targets) == 4
    assert "LON" in targets or "FRA" in targets  # the designed hubs


def test_end_to_end_toy_run():
    g = build_toy_graph()
    res = simulate(g, _run(StrategyConfig(name=StrategyName.BETWEENNESS, budget=4)))
    assert res.summary["peak_infected"] > 0
    assert len(res.timeseries["I"]) == 30


def test_metrics_on_toy():
    g = build_toy_graph()
    char = characterize(g)
    db = degree_betweenness(g)
    assert char["n_nodes"] == 12
    assert -1.0 <= db["spearman_deg_btw"] <= 1.0

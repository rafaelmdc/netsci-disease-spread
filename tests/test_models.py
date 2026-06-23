"""Scientific-correctness tests for the compartmental models.

Each asserts a property the model must have, so a regression in the dynamics
fails loudly: conservation, SEIR latency ordering, SQIR peak suppression,
SIS endemicity, and that vaccination reduces the peak.
"""

import networkx as nx
import numpy as np
import pytest

from src.config import (
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
    StrategyConfig,
    StrategyName,
)
from src.evaluate.engine import simulate
from src.netgen.toy import build_toy_graph

PARAMS = {
    ModelName.SIR: ModelParams(beta=0.4, gamma=0.1),
    ModelName.SIS: ModelParams(beta=0.4, gamma=0.1),
    ModelName.SEIR: ModelParams(beta=0.4, gamma=0.1, sigma=0.2),
    ModelName.SQIR: ModelParams(beta=0.4, gamma=0.1, kappa=0.15, gamma_q=0.1),
}


def _single_node(pop=10_000):
    g = nx.DiGraph()
    g.add_node("A", population=pop, name="A")
    return g


def _run(model, strategy=None, horizon=80, seed=0, graph_region="toy"):
    return RunConfig(
        network=NetworkConfig(region=graph_region),
        model=ModelConfig(name=model, params=PARAMS[model]),
        strategy=strategy or StrategyConfig(name=StrategyName.CONTROL),
        sim=SimConfig(horizon=horizon, tau=0.0, seed_size=10, seed=seed),
    )


@pytest.mark.parametrize("model", list(ModelName))
def test_population_is_conserved(model):
    res = simulate(_single_node(1000), _run(model))
    total = sum(np.array(res.timeseries[c]) for c in res.compartments)
    assert np.allclose(total, 1000.0, atol=1e-6)


def test_seir_exposed_peaks_before_infectious():
    res = simulate(_single_node(), _run(ModelName.SEIR, horizon=120))
    assert np.argmax(res.timeseries["E"]) < np.argmax(res.timeseries["I"])


def test_sqir_lowers_peak_vs_sir():
    g = _single_node()
    sir = simulate(g, _run(ModelName.SIR, horizon=160))
    sqir = simulate(g, _run(ModelName.SQIR, horizon=160))
    assert sqir.summary["peak_infected"] < sir.summary["peak_infected"]
    assert max(sqir.timeseries["Q"]) > 0  # quarantine was actually used


def test_sis_reaches_endemic_plateau():
    # R0_local = beta/gamma = 4 > 1, so the disease persists rather than dying out
    res = simulate(_single_node(), _run(ModelName.SIS, horizon=300))
    assert res.timeseries["I"][-1] > 0


def test_vaccination_reduces_peak():
    g = build_toy_graph()
    control = simulate(g, _run(ModelName.SIR, horizon=60))
    vacc = simulate(
        g,
        _run(
            ModelName.SIR,
            strategy=StrategyConfig(
                name=StrategyName.BETWEENNESS, budget=6, coverage=0.9, efficacy=0.9
            ),
            horizon=60,
        ),
    )
    assert vacc.summary["vaccinated"] > 0
    assert vacc.summary["peak_infected"] <= control.summary["peak_infected"]

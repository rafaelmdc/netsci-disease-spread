"""Verification of the dynamics against known epidemic theory.

The epidemic threshold is the sharpest qualitative prediction: a well-mixed
SIR outbreak takes off only when R0 = beta/gamma > 1, and the final attack
rate grows with R0. (Exact bond-percolation final-size matching needs a
single-transmissibility model and is a future refinement.)
"""

import networkx as nx
import numpy as np

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


def _attack_rate(beta, gamma, pop=100_000, seed_size=50, horizon=400, steps_per_day=1):
    g = nx.DiGraph()
    g.add_node("A", population=pop, name="A")
    cfg = RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=beta, gamma=gamma)),
        strategy=StrategyConfig(name=StrategyName.CONTROL, budget=0, coverage=0.0, efficacy=0.0),
        sim=SimConfig(
            horizon=horizon, tau=0.0, seed_size=seed_size, seed=0, steps_per_day=steps_per_day
        ),
    )
    res = simulate(g, cfg)
    return 1.0 - res.timeseries["S"][-1] / pop


def test_below_threshold_no_outbreak():
    # R0 = 0.08/0.12 = 0.67 < 1 -> dies out
    assert _attack_rate(0.08, 0.12) < 0.02


def test_above_threshold_large_outbreak():
    # R0 = 0.4/0.1 = 4 -> major epidemic
    assert _attack_rate(0.4, 0.1) > 0.5


def test_attack_rate_increases_with_R0():
    assert _attack_rate(0.36, 0.12) > _attack_rate(0.18, 0.12)


def test_final_size_matches_percolation_equation():
    # Mean-field SIR final size solves z = 1 - exp(-R0 z) (equivalently the
    # bond-percolation outbreak size). With fine sub-stepping the discrete
    # engine converges to this continuous result.
    from scipy.optimize import brentq

    r0, gamma = 2.0, 0.1
    expected = brentq(lambda z: z - (1 - np.exp(-r0 * z)), 1e-6, 1 - 1e-9)
    got = _attack_rate(r0 * gamma, gamma, seed_size=1, horizon=800, steps_per_day=20)
    assert abs(got - expected) < 0.03

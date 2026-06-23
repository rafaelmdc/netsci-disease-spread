import networkx as nx
import numpy as np

from src.config import ModelConfig, ModelName, ModelParams, NetworkConfig, RunConfig, SimConfig
from src.evaluate.engine import simulate
from src.evaluate.models.sir import SIR


def _single_node_run(seed=0):
    return RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.4, gamma=0.1)),
        sim=SimConfig(horizon=50, tau=0.0, seed_size=10, seed=seed),
    )


def _single_node_graph(pop=1000):
    g = nx.DiGraph()
    g.add_node("A", population=pop, name="A")
    return g


def test_reaction_one_step_matches_formula():
    model = SIR()
    pop = np.array([1000.0])
    state = model.init_state(pop, seed_node=0, seed_size=100.0)
    params = ModelParams(beta=0.4, gamma=0.1)
    nxt = model.reaction(state, params)
    # expected new infections = beta * S * I / N
    s, i = state["S"][0], state["I"][0]
    expected_inf = params.beta * s * i / (s + i)
    assert nxt["I"][0] == np.float64(i + expected_inf - params.gamma * i)


def test_conservation_single_node():
    g = _single_node_graph(pop=1000)
    res = simulate(g, _single_node_run())
    ts = res.timeseries
    totals = np.array(ts["S"]) + np.array(ts["I"]) + np.array(ts["R"])
    assert np.allclose(totals, 1000.0, atol=1e-6)


def test_outbreak_grows_then_recovers():
    g = _single_node_graph(pop=1000)
    res = simulate(g, _single_node_run())
    infected = res.timeseries["I"]
    assert max(infected) > infected[0]              # it grew
    assert res.summary["final_recovered"] > 0       # someone recovered


def test_determinism_same_seed():
    g = _single_node_graph()
    a = simulate(g, _single_node_run(seed=7))
    b = simulate(g, _single_node_run(seed=7))
    assert a.timeseries == b.timeseries


def test_per_layer_edge_rate():
    from src.config import SimConfig
    from src.evaluate.engine import _edge_rate

    data = {"w_air": 10.0, "w_land": 5.0, "weight": 15.0}
    sim = SimConfig(tau=0.001, tau_by_layer={"air": 0.001, "land": 0.01})
    # 0.001*10 (air) + 0.01*5 (land) = 0.06
    assert abs(_edge_rate(data, sim) - 0.06) < 1e-9


def test_global_tau_fallback():
    from src.config import SimConfig
    from src.evaluate.engine import _edge_rate

    sim = SimConfig(tau=0.001)
    assert abs(_edge_rate({"weight": 15.0}, sim) - 0.015) < 1e-9

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
    s, i = state["S"][0], state["I"][0]
    pressure = np.array([i / (s + i)])  # local infectious fraction
    nxt = model.reaction(state, params, pressure)
    # expected new infections = beta * pressure * S = beta * S * I / N
    expected_inf = params.beta * pressure[0] * s
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


def _multi_city_run(horizon):
    return RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.4, gamma=0.1)),
        sim=SimConfig(horizon=horizon, tau=0.01, seed_size=50, seed=0),
    )


def _three_city_graph():
    g = nx.DiGraph()
    for n, pop in {"A": 100_000, "B": 100_000, "C": 100_000}.items():
        g.add_node(n, population=pop, name=n)
    for a, b in [("A", "B"), ("B", "A"), ("B", "C"), ("C", "B")]:
        g.add_edge(a, b, weight=1.0)
    return g


def test_progress_callback_fires_once_per_day():
    g = _three_city_graph()
    seen = []
    res = simulate(g, _multi_city_run(30), progress=lambda d, t: seen.append((d, t)))
    days = [d for d, _ in seen]
    assert days == list(range(30))  # one call per day, in order
    # the totals handed to the callback match the recorded series each day
    for d, totals in seen:
        for c in res.compartments:
            assert totals[c] == res.timeseries[c][d]


def test_continue_matches_one_long_run():
    g = _three_city_graph()
    full = simulate(g, _multi_city_run(80))

    part1 = simulate(g, _multi_city_run(50))
    part2 = simulate(
        g, _multi_city_run(30), init_state=part1.final_state, day_offset=50
    )

    for c in full.compartments:
        joined = part1.timeseries[c] + part2.timeseries[c]
        assert np.allclose(joined, full.timeseries[c], atol=1e-9)


def test_continue_progress_day_offset():
    g = _three_city_graph()
    part1 = simulate(g, _multi_city_run(50))
    days = []
    simulate(
        g, _multi_city_run(30), init_state=part1.final_state, day_offset=50,
        progress=lambda d, t: days.append(d),
    )
    assert days == list(range(50, 80))  # resumed days are numbered after the original


def test_diffusion_rate_excludes_land():
    from src.config import SimConfig
    from src.evaluate.engine import diffusion_rate

    # diffusion is air+water only; land is recurrent (commuting), not relocation
    data = {"w_air": 10.0, "w_water": 2.0, "w_land": 5.0}
    sim = SimConfig(tau=0.001, tau_by_layer={"air": 0.001, "water": 0.01, "land": 0.3})
    # 0.001*10 (air) + 0.01*2 (water) = 0.03 ; land excluded
    assert abs(diffusion_rate(data, sim) - 0.03) < 1e-9


def test_global_tau_fallback():
    from src.config import SimConfig
    from src.evaluate.engine import diffusion_rate

    sim = SimConfig(tau=0.001)
    assert abs(diffusion_rate({"weight": 15.0}, sim) - 0.015) < 1e-9


def test_commuting_matrix_is_row_stochastic_with_stayhome():
    import networkx as nx

    from src.config import SimConfig
    from src.evaluate.engine import _commuting_matrix

    g = nx.DiGraph()
    g.add_node("A", population=1000)
    g.add_node("B", population=1000)
    g.add_edge("A", "B", w_land=0.5, weight=0.5)
    c = _commuting_matrix(g, ["A", "B"], SimConfig(tau_by_layer={"land": 0.4}))
    assert c is not None
    assert np.allclose(c.sum(axis=1), 1.0)  # row-stochastic
    assert c[0, 1] == 0.4 * 0.5  # commuting fraction * kernel
    assert c[0, 0] == 1.0 - 0.4 * 0.5  # stay-home


def test_no_land_means_no_commuting():
    import networkx as nx

    from src.config import SimConfig
    from src.evaluate.engine import _commuting_matrix

    g = nx.DiGraph()
    g.add_node("A", population=1000)
    g.add_edge("A", "A", w_air=1.0)
    assert _commuting_matrix(g, ["A"], SimConfig()) is None


def _two_city_water_graph():
    import networkx as nx

    g = nx.DiGraph()
    g.add_node("A", population=100_000, lat=40.0, lon=0.0)
    g.add_node("B", population=100_000, lat=49.0, lon=0.0)  # ~1000 km
    for a, b in [("A", "B"), ("B", "A")]:
        g.add_edge(a, b, layer="water", w_water=1.0, weight=1.0)
    return g


def _water_run(transit):
    from src.config import (
        Layer,
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

    cfg = RunConfig(
        network=NetworkConfig(region="toy", layers=[Layer.WATER]),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.3, gamma=0.12)),
        strategy=StrategyConfig(name=StrategyName.CONTROL, budget=0, coverage=0.0, efficacy=0.0),
        sim=SimConfig(
            horizon=150, seed=0, seed_size=50, tau_by_layer={"water": 0.02}, transit=transit
        ),
    )
    return simulate(_two_city_water_graph(), cfg)


def test_in_transit_transmission_and_onboard_control():
    base = _water_run(None)
    intense = _water_run({"water": {"beta": 2.0}})
    controlled = _water_run({"water": {"beta": 2.0, "control": 0.9}})
    # in-transit super-spreading raises the peak; onboard control brings it back
    assert intense.summary["peak_infected"] > base.summary["peak_infected"]
    assert controlled.summary["peak_infected"] < intense.summary["peak_infected"]
    # population conserved with transit on
    total = sum(intense.timeseries[c][-1] for c in intense.compartments)
    assert abs(total - 200_000) < 1e-3


def test_recurrent_commuting_couples_without_relocating():
    # A is seeded; A<->B linked only by land (commuting). B should become
    # infected via shared-location mixing, yet no air/water => no relocation,
    # so each city's total population stays put.
    import networkx as nx

    from src.config import (
        Layer,
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

    g = nx.DiGraph()
    g.add_node("A", population=10_000)
    g.add_node("B", population=10_000)
    g.add_edge("A", "B", w_land=0.5, weight=0.5)
    g.add_edge("B", "A", w_land=0.5, weight=0.5)
    cfg = RunConfig(
        network=NetworkConfig(region="toy", layers=[Layer.AIR, Layer.LAND]),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.5, gamma=0.1)),
        strategy=StrategyConfig(name=StrategyName.CONTROL, budget=0, coverage=0.0, efficacy=0.0),
        sim=SimConfig(horizon=120, seed_size=20, seed=0, tau_by_layer={"land": 0.3}),
    )
    res = simulate(g, cfg, record_nodes=True)
    # B got infected purely through commuting coupling
    assert res.node_infectious[-1][1] > 0 or max(s[1] for s in res.node_infectious) > 0
    # population conserved (no relocation: total stays 20000)
    total = sum(res.timeseries[c][-1] for c in res.compartments)
    assert abs(total - 20_000) < 1e-6

"""Air-interdiction transforms and scenario runner."""

import networkx as nx

from src.config import (
    Layer,
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
)
from src.evaluate.interdiction import close_airports, close_layer, run_scenarios, scenarios


def _multilayer() -> nx.DiGraph:
    """A-B connected only by air; B-C only by land."""
    g = nx.DiGraph()
    coords = {"A": (40.0, -3.0), "B": (48.0, 2.0), "C": (52.0, 13.0)}
    for n, (lat, lon) in coords.items():
        g.add_node(n, population=100_000, name=n, lat=lat, lon=lon)
    g.add_edge("A", "B", w_air=1.0, w_land=0.0, w_water=0.0)
    g.add_edge("B", "A", w_air=1.0, w_land=0.0, w_water=0.0)
    g.add_edge("B", "C", w_air=0.0, w_land=2.0, w_water=0.0)
    g.add_edge("C", "B", w_air=0.0, w_land=2.0, w_water=0.0)
    return g


def test_close_layer_air_removes_air_only_edges_keeps_land():
    g = close_layer(_multilayer(), "air")
    assert not g.has_edge("A", "B")  # air-only edge gone
    assert g.has_edge("B", "C")  # land edge survives
    assert g.number_of_edges() == 2


def test_close_layer_generic_air_graph():
    g = nx.DiGraph()
    g.add_node("A", population=1, name="A", lat=0, lon=0)
    g.add_node("B", population=1, name="B", lat=1, lon=1)
    g.add_edge("A", "B", weight=3.0)  # generic == air route
    assert close_layer(g, "air").number_of_edges() == 0


def test_close_airports_zeros_incident_air_keeps_land():
    g = close_airports(_multilayer(), ["A"])
    assert not g.has_edge("A", "B")  # A's flights stopped
    assert g.has_edge("B", "C")  # unrelated land link intact


def _cfg() -> RunConfig:
    return RunConfig(
        network=NetworkConfig(region="toy", layers=[Layer.AIR, Layer.LAND]),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.4, gamma=0.1)),
        sim=SimConfig(horizon=30, tau=0.001, tau_by_layer={"air": 0.001, "land": 0.2},
                      seed_size=50, seed=0),
    )


def test_run_scenarios_returns_all_five():
    res = run_scenarios(_multilayer(), _cfg(), k=1)
    assert len(res) == 5
    assert all("summary" in r and "infectious" in r for r in res.values())


def test_fully_closed_contains_more_than_full_network():
    res = run_scenarios(_multilayer(), _cfg(), k=1)
    full = next(v for k, v in res.items() if k.startswith("A"))
    air_only_closed = next(v for k, v in res.items() if k.startswith("C"))
    # C shuts every layer -> no inter-city mobility -> no larger than the full net
    assert air_only_closed["summary"]["peak_infected"] <= full["summary"]["peak_infected"]


def test_scenarios_are_graph_copies_not_mutations():
    g = _multilayer()
    before = g.number_of_edges()
    scenarios(g, k=1)
    assert g.number_of_edges() == before  # original untouched

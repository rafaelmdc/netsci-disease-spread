"""Visualization layer: per-node recording, figure builders, run catalogue."""

import json

import networkx as nx
import pandas as pd

from src.config import (
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
)
from src.evaluate.engine import simulate
from src.viz.catalog import scan_runs
from src.viz.compare_html import strategy_panel_figure
from src.viz.curves_html import curves_figure
from src.viz.interdiction_html import interdiction_figure
from src.viz.spread_html import spread_figure
from src.viz.structure_html import structure_figure


def _line_graph() -> nx.DiGraph:
    """Three connected cities with coordinates, so infection can diffuse."""
    g = nx.DiGraph()
    for n, (lat, lon) in {"A": (40.0, -3.0), "B": (48.0, 2.0), "C": (52.0, 13.0)}.items():
        g.add_node(n, population=100_000, name=n, lat=lat, lon=lon)
    g.add_edge("A", "B", weight=1.0)
    g.add_edge("B", "A", weight=1.0)
    g.add_edge("B", "C", weight=1.0)
    g.add_edge("C", "B", weight=1.0)
    return g


def _run(horizon=20):
    return RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.4, gamma=0.1)),
        sim=SimConfig(horizon=horizon, tau=0.01, seed_size=50, seed=0),
    )


def test_engine_records_per_node_history():
    g = _line_graph()
    res = simulate(g, _run(horizon=15), record_nodes=True)
    assert res.node_infectious is not None
    assert len(res.node_infectious) == 15  # one snapshot per day
    assert all(arr.shape == (3,) for arr in res.node_infectious)  # one value per node


def test_record_nodes_off_by_default():
    res = simulate(_line_graph(), _run())
    assert res.node_infectious is None


def test_save_node_timeseries_written(tmp_path, monkeypatch):
    out = tmp_path / "node_timeseries.parquet"
    monkeypatch.setattr("src.evaluate.runner.run_node_timeseries", lambda *a, **k: out)
    monkeypatch.setattr("src.evaluate.runner.run_json", lambda *a, **k: tmp_path / "summary.json")
    monkeypatch.setattr(
        "src.evaluate.runner.run_timeseries", lambda *a, **k: tmp_path / "timeseries.parquet"
    )
    monkeypatch.setattr("src.evaluate.runner.run_state", lambda *a, **k: tmp_path / "state.npz")
    from src.evaluate.runner import run_and_save

    run_and_save(_run(), _line_graph(), record_nodes=True)
    assert out.exists()
    df = pd.read_parquet(out)
    assert set(df.columns) == {"day", "node", "name", "lat", "lon", "infectious"}
    assert df["day"].nunique() == 20


def test_spread_figure_has_a_frame_per_day():
    df = pd.DataFrame(
        {
            "day": [0, 0, 1, 1],
            "node": ["A", "B", "A", "B"],
            "name": ["A", "B", "A", "B"],
            "lat": [40.0, 48.0, 40.0, 48.0],
            "lon": [-3.0, 2.0, -3.0, 2.0],
            "infectious": [10.0, 0.0, 8.0, 5.0],
        }
    )
    fig = spread_figure(df, title="t")
    assert len(fig.frames) == 2
    assert fig.data  # base trace present


def test_curves_figure_builds():
    ts = pd.DataFrame({"S": [100, 90], "I": [0, 10], "R": [0, 0]})
    fig = curves_figure(ts, title="t")
    assert len(fig.data) >= 3


def test_structure_figure_flags_anomalous():
    # star + a low-degree bridge: B has few links but sits on many shortest paths
    g = nx.DiGraph()
    for n in "ABCDEF":
        g.add_node(n, name=n, lat=0.0, lon=0.0)
    for a, b in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")]:
        g.add_edge(a, b)
        g.add_edge(b, a)
    fig = structure_figure(g, title="t")
    assert len(fig.data) == 2  # typical + anomalous traces


def test_strategy_panel_figure_builds():
    df = pd.DataFrame(
        {
            "model": ["sir", "sir", "seir", "seir"],
            "strategy": ["control", "degree", "control", "degree"],
            "coverage": [0.0, 0.75, 0.0, 0.75],
            "peak_infected": [100, 60, 90, 55],
        }
    )
    fig = strategy_panel_figure(df, title="t")
    assert fig.data


def test_interdiction_figure_builds():
    results = {
        "A · full": {"infectious": [1, 5, 3], "summary": {"peak_infected": 5}},
        "B · air closed": {"infectious": [1, 3, 2], "summary": {"peak_infected": 3}},
        "C · air-only": {"infectious": [1, 1, 1], "summary": {"peak_infected": 1}},
    }
    fig = interdiction_figure(results, title="t")
    assert len(fig.data) == 3


def test_catalog_scans_runs(tmp_path):
    run = tmp_path / "europe" / "air" / "sir_control_seed0_abc123"
    run.mkdir(parents=True)
    summary = {
        "label": "sir_control_seed0_abc123",
        "config": {
            "network": {"region": "europe", "layers": ["air"]},
            "model": {"name": "sir"},
            "strategy": {"name": "control", "coverage": 0.0},
            "sim": {"seed": 0},
        },
        "summary": {"peak_infected": 1234.0},
    }
    (run / "summary.json").write_text(json.dumps(summary))
    entries = scan_runs(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert e.region == "europe" and e.model == "sir" and e.has_nodes is False
    (run / "node_timeseries.parquet").write_text("")  # presence flips the flag
    assert scan_runs(tmp_path)[0].has_nodes is True

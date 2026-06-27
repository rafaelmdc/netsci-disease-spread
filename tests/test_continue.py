"""Continuing ('add days') a finished run appends in place and stays exact."""

import json

import networkx as nx
import numpy as np
import pandas as pd

from src.config import ModelConfig, ModelName, ModelParams, NetworkConfig, RunConfig, SimConfig


def _graph() -> nx.DiGraph:
    g = nx.DiGraph()
    for n in ("A", "B", "C"):
        g.add_node(n, population=100_000, name=n, lat=40.0, lon=0.0)
    for a, b in [("A", "B"), ("B", "A"), ("B", "C"), ("C", "B")]:
        g.add_edge(a, b, weight=1.0)
    return g


def _run(horizon):
    return RunConfig(
        network=NetworkConfig(region="toy"),
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.4, gamma=0.1)),
        sim=SimConfig(horizon=horizon, tau=0.01, seed_size=50, seed=0),
    )


def _patch_paths(tmp_path, monkeypatch):
    for name, fname in {
        "run_json": "summary.json",
        "run_timeseries": "timeseries.parquet",
        "run_node_timeseries": "node_timeseries.parquet",
        "run_state": "state.npz",
    }.items():
        monkeypatch.setattr(f"src.evaluate.runner.{name}", lambda *a, f=fname, **k: tmp_path / f)


def test_continue_appends_and_matches_long_run(tmp_path, monkeypatch):
    from src.evaluate.engine import simulate
    from src.evaluate.runner import continue_run, run_and_save

    _patch_paths(tmp_path, monkeypatch)
    g = _graph()

    run_and_save(_run(50), g, record_nodes=True)
    record = continue_run("toy", "air", _run(50).label, extra_days=30, graph=g, record_nodes=True)

    # horizon + lineage bookkeeping updated in place
    assert record["config"]["sim"]["horizon"] == 80
    assert record["lineage"]["segments"] == [50, 30]

    # the appended series equals one 80-day run, day for day
    ts = pd.read_parquet(tmp_path / "timeseries.parquet")
    assert len(ts) == 80
    full = simulate(g, _run(80))
    for c in full.compartments:
        assert np.allclose(ts[c].to_numpy(), full.timeseries[c], atol=1e-9)

    # node history was extended to cover the new days too
    nodes = pd.read_parquet(tmp_path / "node_timeseries.parquet")
    assert nodes["day"].max() == 79

    # summary.json on disk reflects the refreshed record
    assert json.loads((tmp_path / "summary.json").read_text())["config"]["sim"]["horizon"] == 80

"""Run one experiment and persist its results — shared by the CLI and the sweep.

Keeping this in one place means a single, identical I/O contract whether a
run is launched on its own or as one cell of a parameter sweep.
"""

from __future__ import annotations

import json
import platform

import networkx as nx
import numpy as np
import pandas as pd

from src.config import RunConfig
from src.evaluate.engine import simulate
from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import (
    combo_name,
    ensure_parent,
    processed_graph,
    run_json,
    run_node_timeseries,
    run_timeseries,
)


def resolve_graph_path(cfg: RunConfig):
    if cfg.network.graph_path:
        return cfg.network.graph_path
    return processed_graph(cfg.network.region, _combo(cfg))


def _combo(cfg: RunConfig) -> str:
    return combo_name([layer.value for layer in cfg.network.layers])


def run_and_save(
    cfg: RunConfig, graph: nx.DiGraph | None = None, record_nodes: bool = False
) -> dict:
    """Simulate one run and persist it. When ``record_nodes`` is set, also
    write the per-node, per-day infection history (``node_timeseries.parquet``)
    that the geo-animation consumes — opt-in, since storing per-node x per-day
    for every run in a sweep would be wasteful."""
    if graph is None:
        graph = read_graphml(resolve_graph_path(cfg))

    result = simulate(graph, cfg, record_nodes=record_nodes)
    combo = _combo(cfg)

    record = {
        "label": cfg.label,
        "run_id": cfg.run_id,
        "config": cfg.model_dump(mode="json"),
        "versions": {"python": platform.python_version()},
        "network": characterize(graph),
        "structural": degree_betweenness(graph),
        "targets": result.targets,
        "seed_node": result.seed_node,
        "summary": result.summary,
    }

    out_json = run_json(cfg.network.region, combo, cfg.label)
    ensure_parent(out_json)
    out_json.write_text(json.dumps(record, indent=2))

    ts = pd.DataFrame(result.timeseries)
    ts.index.name = "day"
    ts.to_parquet(run_timeseries(cfg.network.region, combo, cfg.label))

    if record_nodes and result.node_infectious is not None:
        _save_node_timeseries(graph, result, cfg.network.region, combo, cfg.label)
    return record


def _save_node_timeseries(graph, result, region: str, combo: str, label: str) -> None:
    """Tidy long table [day, node, name, lat, lon, infectious] for animation.

    Nodes that never carry infection are dropped (they only bloat the file);
    the network backdrop is drawn from the graph itself by the viz layer."""
    inf = np.array(result.node_infectious)  # (days, n_nodes)
    keep = inf.max(axis=0) > 0.5  # at least one whole person, at some point
    nodes = result.nodes
    days, idx = inf.shape[0], np.where(keep)[0]
    name = {n: str(graph.nodes[n].get("name", n)) for n in nodes}
    lat = {n: float(graph.nodes[n].get("lat", 0.0)) for n in nodes}
    lon = {n: float(graph.nodes[n].get("lon", 0.0)) for n in nodes}

    frames = []
    for d in range(days):
        for i in idx:
            n = nodes[i]
            frames.append((d, n, name[n], lat[n], lon[n], float(inf[d, i])))
    df = pd.DataFrame(frames, columns=["day", "node", "name", "lat", "lon", "infectious"])
    df.to_parquet(run_node_timeseries(region, combo, label))

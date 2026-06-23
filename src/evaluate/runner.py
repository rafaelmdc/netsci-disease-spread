"""Run one experiment and persist its results — shared by the CLI and the sweep.

Keeping this in one place means a single, identical I/O contract whether a
run is launched on its own or as one cell of a parameter sweep.
"""

from __future__ import annotations

import json
import platform

import networkx as nx
import pandas as pd

from src.config import RunConfig
from src.evaluate.engine import simulate
from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import combo_name, ensure_parent, processed_graph, run_json, run_timeseries


def resolve_graph_path(cfg: RunConfig):
    if cfg.network.graph_path:
        return cfg.network.graph_path
    return processed_graph(cfg.network.region, _combo(cfg))


def _combo(cfg: RunConfig) -> str:
    return combo_name([layer.value for layer in cfg.network.layers])


def run_and_save(cfg: RunConfig, graph: nx.DiGraph | None = None) -> dict:
    if graph is None:
        graph = read_graphml(resolve_graph_path(cfg))

    result = simulate(graph, cfg)
    combo = _combo(cfg)

    record = {
        "run_id": cfg.run_id,
        "config": cfg.model_dump(mode="json"),
        "versions": {"python": platform.python_version()},
        "network": characterize(graph),
        "structural": degree_betweenness(graph),
        "targets": result.targets,
        "seed_node": result.seed_node,
        "summary": result.summary,
    }

    out_json = run_json(cfg.network.region, combo, cfg.run_id)
    ensure_parent(out_json)
    out_json.write_text(json.dumps(record, indent=2))

    ts = pd.DataFrame(result.timeseries)
    ts.index.name = "day"
    ts.to_parquet(run_timeseries(cfg.network.region, combo, cfg.run_id))
    return record

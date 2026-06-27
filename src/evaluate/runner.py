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
from src.evaluate.engine import ProgressFn, State, simulate, summarize
from src.evaluate.metrics import characterize, degree_betweenness
from src.evaluate.models import get_model
from src.netgen.graph_io import read_graphml
from src.paths import (
    combo_name,
    ensure_parent,
    processed_graph,
    run_json,
    run_node_timeseries,
    run_state,
    run_timeseries,
)


def resolve_graph_path(cfg: RunConfig):
    if cfg.network.graph_path:
        return cfg.network.graph_path
    return processed_graph(cfg.network.region, _combo(cfg))


def _combo(cfg: RunConfig) -> str:
    return combo_name([layer.value for layer in cfg.network.layers])


def run_and_save(
    cfg: RunConfig,
    graph: nx.DiGraph | None = None,
    record_nodes: bool = False,
    progress: ProgressFn | None = None,
) -> dict:
    """Simulate one run and persist it. When ``record_nodes`` is set, also
    write the per-node, per-day infection history (``node_timeseries.parquet``)
    that the geo-animation consumes — opt-in, since storing per-node x per-day
    for every run in a sweep would be wasteful. ``progress`` is forwarded to the
    engine so a caller (e.g. the dashboard) can stream the run day-by-day.

    A ``state.npz`` resume checkpoint is always written so the run can later be
    continued for more days (see :func:`continue_run`)."""
    if graph is None:
        graph = read_graphml(resolve_graph_path(cfg))

    result = simulate(graph, cfg, record_nodes=record_nodes, progress=progress)
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
        "lineage": {"segments": [cfg.sim.horizon]},
    }

    out_json = run_json(cfg.network.region, combo, cfg.label)
    ensure_parent(out_json)
    out_json.write_text(json.dumps(record, indent=2))

    ts = pd.DataFrame(result.timeseries)
    ts.index.name = "day"
    ts.to_parquet(run_timeseries(cfg.network.region, combo, cfg.label))

    if record_nodes and result.node_infectious is not None:
        _save_node_timeseries(graph, result, cfg.network.region, combo, cfg.label)
    _save_state(result, list(graph.nodes()), cfg.network.region, combo, cfg.label)
    return record


def _save_state(result, nodes: list[str], region: str, combo: str, label: str) -> None:
    """Write the resume checkpoint: each compartment array + the node order."""
    if result.final_state is None:
        return
    arrays = {c: arr for c, arr in result.final_state.items()}
    np.savez(ensure_parent(run_state(region, combo, label)), _nodes=np.array(nodes), **arrays)


def _load_state(nodes: list[str], region: str, combo: str, label: str) -> State:
    """Load a checkpoint, reindexing onto the current graph's node order."""
    data = np.load(run_state(region, combo, label), allow_pickle=False)
    saved = list(data["_nodes"])
    comps = [k for k in data.files if k != "_nodes"]
    if saved == nodes:
        return {c: data[c] for c in comps}
    pos = {n: i for i, n in enumerate(saved)}
    order = [pos[n] for n in nodes]  # KeyError => graph changed, fail loudly
    return {c: data[c][order] for c in comps}


def continue_run(
    region: str,
    combo: str,
    label: str,
    extra_days: int,
    graph: nx.DiGraph | None = None,
    record_nodes: bool = True,
    progress: ProgressFn | None = None,
) -> dict:
    """Resume a finished run for ``extra_days`` more days, **appending** to its
    time series / node history in place and updating the summary + horizon.

    Returns the refreshed ``summary.json`` record. ``progress`` day indices
    continue from the run's current horizon."""
    out_json = run_json(region, combo, label)
    record = json.loads(out_json.read_text())
    cfg = RunConfig.model_validate(record["config"])
    if graph is None:
        graph = read_graphml(resolve_graph_path(cfg))

    nodes = list(graph.nodes())
    elapsed = int(cfg.sim.horizon)
    init_state = _load_state(nodes, region, combo, label)

    more = cfg.model_copy(deep=True)
    more.sim.horizon = extra_days
    result = simulate(
        graph, more, record_nodes=record_nodes, progress=progress,
        init_state=init_state, day_offset=elapsed,
    )

    # append the new days to the on-disk time series
    ts_path = run_timeseries(region, combo, label)
    old_ts = pd.read_parquet(ts_path)
    new_ts = pd.DataFrame(result.timeseries)
    full_ts = pd.concat([old_ts, new_ts], ignore_index=True)
    full_ts.index.name = "day"
    full_ts.to_parquet(ts_path)

    if record_nodes and result.node_infectious is not None:
        _append_node_timeseries(graph, result, elapsed, region, combo, label)

    model = get_model(cfg.model.name)
    record["summary"] = summarize({c: full_ts[c].tolist() for c in full_ts.columns}, model,
                                  record["summary"]["total_population"])
    record["config"]["sim"]["horizon"] = elapsed + extra_days
    record.setdefault("lineage", {"segments": [elapsed]})
    record["lineage"]["segments"].append(extra_days)
    out_json.write_text(json.dumps(record, indent=2))

    _save_state(result, nodes, region, combo, label)
    return record


def _node_frame(graph, result, day_offset: int = 0) -> pd.DataFrame:
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
            frames.append((day_offset + d, n, name[n], lat[n], lon[n], float(inf[d, i])))
    return pd.DataFrame(frames, columns=["day", "node", "name", "lat", "lon", "infectious"])


def _save_node_timeseries(graph, result, region: str, combo: str, label: str) -> None:
    _node_frame(graph, result).to_parquet(run_node_timeseries(region, combo, label))


def _append_node_timeseries(graph, result, day_offset, region, combo, label) -> None:
    """Append the resumed days to an existing node history (or create it)."""
    new = _node_frame(graph, result, day_offset)
    path = run_node_timeseries(region, combo, label)
    if path.exists():
        new = pd.concat([pd.read_parquet(path), new], ignore_index=True)
    new.to_parquet(path)

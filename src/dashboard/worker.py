"""arq worker — runs simulations off the queue and streams them day-by-day.

One job at a time (a simulation is CPU-bound and resource-heavy). The sync engine
runs in a thread so the worker's event loop stays responsive; its per-day
``progress`` callback publishes to Redis (sync, from that thread), which the
dashboard relays to the browser over SSE. Artifacts are written by the normal
`run_and_save` / `continue_run`, so they land in the usual `results/` tree.
"""

from __future__ import annotations

import asyncio
import time
import traceback

from arq.connections import RedisSettings

from src.config import RunConfig
from src.dashboard import events, jobs
from src.evaluate.interdiction import apply_interdiction
from src.evaluate.models import get_model
from src.evaluate.runner import continue_run, resolve_graph_path, run_and_save
from src.netgen.graph_io import read_graphml
from src.paths import combo_name


def _compartments(cfg: RunConfig) -> list[str]:
    return [*get_model(cfg.model.name).compartments, "V"]


def _progress_cb(job_id: str):
    def cb(day: int, totals: dict[str, float]) -> None:
        events.publish(job_id, {"type": "day", "day": day, "totals": totals})
    return cb


def _node_cb(job_id: str):
    def cb(day: int, infectious) -> None:
        events.publish(job_id, {"type": "geo_day", "day": day,
                                "inf": [int(round(float(x))) for x in infectious]})
    return cb


async def run_simulation(ctx: dict, job_id: str, config: dict) -> None:
    cfg = RunConfig.model_validate(config)
    region = cfg.network.region
    combo = combo_name([layer.value for layer in cfg.network.layers])
    label = cfg.label
    try:
        jobs.mark_running(job_id)
        graph = read_graphml(resolve_graph_path(cfg))
        # edge-level intervention (close layers / ground airports) before the run,
        # so the live map and the saved network stats reflect the interdicted graph
        graph = apply_interdiction(graph, cfg.interdiction)
        events.publish(job_id, {
            "type": "start", "horizon": cfg.sim.horizon, "from_day": 0,
            "compartments": _compartments(cfg),
        })
        # one-time node positions for the live map, then throttled per-node frames
        nodes = list(graph.nodes())
        events.publish(job_id, {
            "type": "geo_init",
            "lat": [round(float(graph.nodes[n].get("lat", 0.0)), 3) for n in nodes],
            "lon": [round(float(graph.nodes[n].get("lon", 0.0)), 3) for n in nodes],
        })
        node_every = max(1, cfg.sim.horizon // 60)  # cap the map at ~60 frames
        record = await asyncio.to_thread(
            run_and_save, cfg, graph, True, _progress_cb(job_id), _node_cb(job_id), node_every
        )
        jobs.mark_done(job_id, region, combo, label)
        events.publish(job_id, {
            "type": "done", "region": region, "combo": combo, "label": label,
            "summary": record["summary"],
        })
    except Exception as exc:  # noqa: BLE001 — report any failure to the UI
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
        events.publish(job_id, {"type": "failed", "error": str(exc)})


async def continue_simulation(
    ctx: dict, job_id: str, region: str, combo: str, label: str, extra_days: int, elapsed: int
) -> None:
    try:
        jobs.mark_running(job_id)
        events.publish(job_id, {
            "type": "start", "horizon": elapsed + extra_days, "from_day": elapsed,
        })
        record = await asyncio.to_thread(
            continue_run, region, combo, label, extra_days, None, True, _progress_cb(job_id)
        )
        jobs.mark_done(job_id, region, combo, label)
        events.publish(job_id, {
            "type": "done", "region": region, "combo": combo, "label": label,
            "summary": record["summary"],
        })
    except Exception as exc:  # noqa: BLE001
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
        events.publish(job_id, {"type": "failed", "error": str(exc)})


def _log(msg: str) -> None:
    """Print a timestamped line straight to the worker's stdout (docker logs)."""
    print(f"[data] {time.strftime('%H:%M:%S')} {msg}", flush=True)


def _data_action(action: str, region: str | None, layers: list[str] | None) -> None:
    """Run one data-prep step synchronously (called in a thread)."""
    _log(f"action={action!r} region={region!r} layers={layers!r} — start")
    if action == "retrieve":
        from src.retrieve.geonames import fetch as fetch_geonames
        from src.retrieve.openflights import fetch as fetch_openflights
        from src.retrieve.osm_ferries import fetch as fetch_ferries
        _log("fetching OpenFlights (airports + routes)…")
        fetch_openflights()
        _log("fetching GeoNames (cities)…")
        fetch_geonames()
        _log("fetching OSM ferries…")
        fetch_ferries()
    elif action == "netgen_all":
        from src.experiment import load_experiment_config
        from src.netgen.build import build_network
        from src.netgen.graph_io import write_graphml
        from src.paths import ROOT, combo_name, processed_graph
        exp = load_experiment_config(ROOT / "experiment.yaml")
        nets = list(exp.networks())
        _log(f"building {len(nets)} network(s)…")
        for i, net in enumerate(nets, 1):
            combo = combo_name([layer.value for layer in net.layers])
            _log(f"[{i}/{len(nets)}] building {net.region}/{combo}…")
            graph = build_network(net)
            out = processed_graph(net.region, combo)
            write_graphml(graph, out)
            _log(f"[{i}/{len(nets)}] {net.region}/{combo}: "
                 f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges → {out}")
    elif action == "netgen_one":
        from src.config import Layer, NetworkConfig
        from src.netgen.build import build_network
        from src.netgen.graph_io import write_graphml
        from src.paths import combo_name, processed_graph
        chosen = layers or ["air"]
        cfg = NetworkConfig(region=region, layers=[Layer(x) for x in chosen])
        _log(f"building {region}/{combo_name(chosen)}…")
        graph = build_network(cfg)
        out = processed_graph(region, combo_name(chosen))
        write_graphml(graph, out)
        _log(f"{region}/{combo_name(chosen)}: "
             f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges → {out}")
    elif action == "sweep":
        from src.evaluate.metrics import betweenness
        from src.evaluate.runner import run_and_save
        from src.experiment import load_experiment_config
        from src.netgen.graph_io import read_graphml
        from src.paths import ROOT, processed_graph
        exp = load_experiment_config(ROOT / "experiment.yaml")
        groups = exp.grouped_by_network()
        total = sum(len(c) for c in groups.values())
        _log(f"running {total} simulation(s) across {len(groups)} network(s)…")
        done = 0
        for (region, combo), cfgs in groups.items():
            _log(f"network {region}/{combo}: reading graph + warming betweenness…")
            graph = read_graphml(processed_graph(region, combo))
            betweenness(graph)  # warm the cache once before the runs share the graph
            for cfg in cfgs:
                run_and_save(cfg, graph, record_nodes=False)
                done += 1
                _log(f"[{done}/{total}] ran {region}/{combo} :: {cfg.label}")
    elif action == "collect":
        from src.evaluate.aggregate import collect
        _log("collecting per-run results into the master table…")
        collect()
    elif action == "structure":
        from src.evaluate.aggregate import structure_table
        _log("building the structure (network-metrics) table…")
        structure_table()
    elif action == "aggregate":
        from src.evaluate.aggregate import collect, structure_table
        _log("collecting per-run results…")
        collect()
        _log("building the structure table…")
        structure_table()
    else:
        raise ValueError(f"unknown data action: {action}")
    _log(f"action={action!r} — done")


async def run_data_task(
    ctx: dict, job_id: str, action: str, region: str | None = None,
    layers: list[str] | None = None,
) -> None:
    try:
        jobs.mark_running(job_id)
        await asyncio.to_thread(_data_action, action, region, layers)
        jobs.update_job(job_id, status="done", finished_at=time.time())
    except Exception as exc:  # noqa: BLE001
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")


def _study(job_id: str, config_path: str, maps: bool) -> None:
    """Expand the generated config into its grid and run each cell, in a thread."""
    from src.evaluate.aggregate import collect, structure_table
    from src.evaluate.metrics import betweenness
    from src.evaluate.runner import run_and_save
    from src.experiment import load_experiment_config
    from src.netgen.graph_io import read_graphml
    from src.paths import processed_graph

    exp = load_experiment_config(config_path)
    groups = exp.grouped_by_network()
    total = sum(len(v) for v in groups.values())
    events.publish(job_id, {"type": "study_start", "total": total})

    done = 0
    for (region, combo), cfgs in groups.items():
        graph = read_graphml(processed_graph(region, combo))
        betweenness(graph)  # warm the cache once, before the runs reuse the graph
        for cfg in cfgs:
            run_and_save(cfg, graph, record_nodes=maps)
            done += 1
            events.publish(job_id, {"type": "run", "done": done, "total": total,
                                    "label": cfg.label, "network": f"{region}/{combo}"})
    collect()
    structure_table()


async def run_study(ctx: dict, job_id: str, config_path: str, maps: bool) -> None:
    """Run a generated multi-run study (a scoped sweep), streaming per-run progress."""
    try:
        jobs.mark_running(job_id)
        await asyncio.to_thread(_study, job_id, config_path, maps)
        jobs.update_job(job_id, status="done", finished_at=time.time())
        events.publish(job_id, {"type": "done"})
    except Exception as exc:  # noqa: BLE001
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
        events.publish(job_id, {"type": "failed", "error": str(exc)})


def _staged_study(job_id: str, config_path: str, maps: bool) -> None:
    """Run the staged protocol (spread -> vaccinate -> re-check), streaming each
    completed run and the stage banners / picked winner to the monitor."""
    import threading

    from src.evaluate.staged import run_staged, staged_total
    from src.experiment import load_experiment_config

    exp = load_experiment_config(config_path)
    total = staged_total(exp)
    events.publish(job_id, {"type": "study_start", "total": total})

    lock, done = threading.Lock(), {"n": 0}

    def on_run(cfg, where: str) -> None:
        with lock:
            done["n"] += 1
            n = done["n"]
        events.publish(job_id, {"type": "run", "done": n, "total": total,
                                "label": cfg.label, "network": where})

    def echo(line: str) -> None:  # stage banners + winner ranking
        events.publish(job_id, {"type": "stage", "msg": line})

    winners = run_staged(exp, maps=maps, echo=echo, on_run=on_run)
    summary = ", ".join(f"{d}->{w.value}" for d, w in winners.items())
    events.publish(job_id, {"type": "stage", "msg": f"best defense per disease: {summary}"})


async def run_staged_study(ctx: dict, job_id: str, config_path: str, maps: bool) -> None:
    """Run the staged protocol from the GUI, streaming stage + per-run progress."""
    try:
        jobs.mark_running(job_id)
        await asyncio.to_thread(_staged_study, job_id, config_path, maps)
        jobs.update_job(job_id, status="done", finished_at=time.time())
        events.publish(job_id, {"type": "done"})
    except Exception as exc:  # noqa: BLE001
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
        events.publish(job_id, {"type": "failed", "error": str(exc)})


class WorkerSettings:
    functions = [run_simulation, continue_simulation, run_data_task, run_study, run_staged_study]
    redis_settings = RedisSettings.from_dsn(events.redis_url())
    max_jobs = 1  # one heavy job at a time
    job_timeout = 6 * 60 * 60  # the full sweep can run for ~an hour; give headroom

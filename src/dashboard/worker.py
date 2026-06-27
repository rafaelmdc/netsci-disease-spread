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


def _data_action(action: str, region: str | None, layers: list[str] | None) -> None:
    """Run one data-prep step synchronously (called in a thread)."""
    if action == "retrieve":
        from src.retrieve.geonames import fetch as fetch_geonames
        from src.retrieve.openflights import fetch as fetch_openflights
        from src.retrieve.osm_ferries import fetch as fetch_ferries
        fetch_openflights()
        fetch_geonames()
        fetch_ferries()
    elif action == "netgen_all":
        from src.config import load_experiment_config
        from src.netgen.build import build_network
        from src.netgen.graph_io import write_graphml
        from src.paths import combo_name, processed_graph
        exp = load_experiment_config("experiment.yaml")
        for net in exp.networks():
            graph = build_network(net)
            combo = combo_name([layer.value for layer in net.layers])
            write_graphml(graph, processed_graph(net.region, combo))
    elif action == "netgen_one":
        from src.config import Layer, NetworkConfig
        from src.netgen.build import build_network
        from src.netgen.graph_io import write_graphml
        from src.paths import combo_name, processed_graph
        chosen = layers or ["air"]
        cfg = NetworkConfig(region=region, layers=[Layer(x) for x in chosen])
        graph = build_network(cfg)
        write_graphml(graph, processed_graph(region, combo_name(chosen)))
    elif action == "sweep":
        from src.evaluate.metrics import betweenness
        from src.evaluate.runner import run_and_save
        from src.experiment import load_experiment_config
        from src.netgen.graph_io import read_graphml
        from src.paths import processed_graph
        exp = load_experiment_config("experiment.yaml")
        for (region, combo), cfgs in exp.grouped_by_network().items():
            graph = read_graphml(processed_graph(region, combo))
            betweenness(graph)  # warm the cache once before the runs share the graph
            for cfg in cfgs:
                run_and_save(cfg, graph, record_nodes=False)
    elif action == "collect":
        from src.evaluate.aggregate import collect
        collect()
    elif action == "structure":
        from src.evaluate.aggregate import structure_table
        structure_table()
    elif action == "aggregate":
        from src.evaluate.aggregate import collect, structure_table
        collect()
        structure_table()
    else:
        raise ValueError(f"unknown data action: {action}")


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


class WorkerSettings:
    functions = [run_simulation, continue_simulation, run_data_task, run_study]
    redis_settings = RedisSettings.from_dsn(events.redis_url())
    max_jobs = 1  # one heavy job at a time
    job_timeout = 6 * 60 * 60  # the full sweep can run for ~an hour; give headroom

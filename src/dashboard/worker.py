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


async def run_pipeline(
    ctx: dict, job_id: str, config: str, interdiction: str, maps: bool
) -> None:
    """Run the full Nextflow pipeline (`-profile local`, no Docker) and stream
    its log to the browser. Stages call the same `netsci` CLI in-process."""
    from src.paths import ROOT
    try:
        jobs.mark_running(job_id)
        events.publish(job_id, {"type": "start_pipeline", "config": config, "maps": maps})
        cmd = [
            "nextflow", "run", "workflow/main.nf", "-profile", "local", "-ansi-log", "false",
            "--config", config, "--interdiction", interdiction,
            "--maps", "true" if maps else "false",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        async for raw in proc.stdout:
            events.publish(job_id, {"type": "log", "line": raw.decode(errors="replace").rstrip()})
        rc = await proc.wait()
        if rc == 0:
            jobs.update_job(job_id, status="done", finished_at=time.time())
            events.publish(job_id, {"type": "done"})
        else:
            jobs.mark_failed(job_id, f"nextflow exited with code {rc}")
            events.publish(job_id, {"type": "failed", "error": f"nextflow exited with code {rc}"})
    except Exception as exc:  # noqa: BLE001
        jobs.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
        events.publish(job_id, {"type": "failed", "error": str(exc)})


class WorkerSettings:
    functions = [run_simulation, continue_simulation, run_data_task, run_pipeline]
    redis_settings = RedisSettings.from_dsn(events.redis_url())
    max_jobs = 1  # one heavy job at a time
    job_timeout = 6 * 60 * 60  # the full sweep can run for ~an hour; give headroom

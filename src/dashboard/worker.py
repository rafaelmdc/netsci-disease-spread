"""arq worker — runs simulations off the queue and streams them day-by-day.

One job at a time (a simulation is CPU-bound and resource-heavy). The sync engine
runs in a thread so the worker's event loop stays responsive; its per-day
``progress`` callback publishes to Redis (sync, from that thread), which the
dashboard relays to the browser over SSE. Artifacts are written by the normal
`run_and_save` / `continue_run`, so they land in the usual `results/` tree.
"""

from __future__ import annotations

import asyncio
import traceback

from arq.connections import RedisSettings

from src.config import RunConfig
from src.dashboard import events, jobs
from src.evaluate.models import get_model
from src.evaluate.runner import continue_run, run_and_save
from src.paths import combo_name


def _compartments(cfg: RunConfig) -> list[str]:
    return [*get_model(cfg.model.name).compartments, "V"]


def _progress_cb(job_id: str):
    def cb(day: int, totals: dict[str, float]) -> None:
        events.publish(job_id, {"type": "day", "day": day, "totals": totals})
    return cb


async def run_simulation(ctx: dict, job_id: str, config: dict) -> None:
    cfg = RunConfig.model_validate(config)
    region = cfg.network.region
    combo = combo_name([layer.value for layer in cfg.network.layers])
    label = cfg.label
    try:
        jobs.mark_running(job_id)
        events.publish(job_id, {
            "type": "start", "horizon": cfg.sim.horizon, "from_day": 0,
            "compartments": _compartments(cfg),
        })
        record = await asyncio.to_thread(run_and_save, cfg, None, True, _progress_cb(job_id))
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


class WorkerSettings:
    functions = [run_simulation, continue_simulation]
    redis_settings = RedisSettings.from_dsn(events.redis_url())
    max_jobs = 1  # one heavy simulation at a time
    job_timeout = 60 * 60  # an hour ceiling for a single run

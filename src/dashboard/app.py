"""FastAPI app for the simulator: design → run (live) → explore.

A thin control plane. Routes enqueue arq jobs and relay their per-day progress
to the browser over SSE; results views reuse the `src.viz` Plotly builders.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as aioredis
import yaml
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import ModelName, StrategyName
from src.dashboard import events, jobs
from src.dashboard.figures import aggregate_context, comparison_context, results_context
from src.dashboard.forms import (
    available_networks,
    build_study_config,
    data_status,
    graph_is_built,
    parse_run_form,
)
from src.experiment import ExperimentConfig
from src.netgen.graph_io import read_graphml
from src.paths import (
    RESULTS,
    combo_name,
    ensure_dir,
    ensure_parent,
    network_gexf,
    processed_graph,
    run_gexf,
    run_json,
    run_node_timeseries,
)
from src.viz.catalog import scan_runs
from src.viz.gephi import network_gexf as build_network_gexf
from src.viz.gephi import run_gexf as build_run_gexf

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.init_db()
    jobs.recover_stale()
    app.state.arq = await create_pool(RedisSettings.from_dsn(events.redis_url()))
    app.state.redis = aioredis.from_url(events.redis_url())
    yield
    await app.state.arq.aclose()
    await app.state.redis.aclose()


app = FastAPI(title="netsci disease-spread simulator", lifespan=lifespan)
app.mount("/files", StaticFiles(directory=str(RESULTS), check_dir=False), name="files")
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


# --- pages ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {
        "jobs": jobs.list_jobs(limit=12),
        "networks": available_networks(),
    })


@app.get("/new", response_class=HTMLResponse)
async def new_form(request: Request):
    return templates.TemplateResponse(request, "new.html", {
        "networks": available_networks(),
        "models": [m.value for m in ModelName],
        "strategies": [s.value for s in StrategyName],
    })


@app.post("/new")
async def submit(request: Request):
    form = await request.form()
    cfg = parse_run_form(form)
    layers = [layer.value for layer in cfg.network.layers]
    if not graph_is_built(cfg.network.region, layers):
        combo = combo_name(layers)
        return templates.TemplateResponse(request, "new.html", {
            "networks": available_networks(),
            "models": [m.value for m in ModelName],
            "strategies": [s.value for s in StrategyName],
            "error": f"Network '{cfg.network.region} / {combo}' is not built. "
                     f"Run `netsci netgen build --region {cfg.network.region} "
                     f"--layers {','.join(layers)}` first.",
        }, status_code=400)

    title = f"{cfg.network.region}/{combo_name(layers)} · {cfg.model.name.value.upper()} · " \
            f"{cfg.strategy.name.value}"
    job_id = jobs.create_job("simulate", title, config_json=json.dumps(cfg.model_dump(mode="json")))
    await app.state.arq.enqueue_job("run_simulation", job_id, cfg.model_dump(mode="json"))
    return RedirectResponse(f"/sim/{job_id}", status_code=303)


@app.get("/sim/{job_id}", response_class=HTMLResponse)
async def sim(request: Request, job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        return HTMLResponse("Unknown job", status_code=404)
    # studies and data tasks have their own views; the console history links here
    if job["kind"] == "study":
        return RedirectResponse(f"/study/{job_id}", status_code=303)
    if job["kind"] == "data":
        return RedirectResponse("/data", status_code=303)
    # finished sims are identified by their artifacts on disk, not the job row
    if job["status"] == "done":
        return RedirectResponse(
            f"/run/{job['region']}/{job['combo']}/{job['label']}", status_code=303)
    return templates.TemplateResponse(request, "monitor.html", {"job": job})


@app.get("/sim/{job_id}/stream")
async def stream(request: Request, job_id: str):
    redis = app.state.redis

    async def gen():
        job = jobs.get_job(job_id)
        if not job:
            return
        if job["status"] in events.TERMINAL:
            yield events.sse({"type": job["status"], "region": job["region"],
                              "combo": job["combo"], "label": job["label"]})
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(events.channel(job_id))
        try:
            # guard the race: if it finished between the check and the subscribe
            job = jobs.get_job(job_id)
            if job["status"] in events.TERMINAL:
                yield events.sse({"type": job["status"], "region": job["region"],
                                  "combo": job["combo"], "label": job["label"]})
                return
            while not await request.is_disconnected():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is None:
                    yield ":keepalive\n\n"
                    continue
                event = json.loads(msg["data"])
                yield events.sse(event)
                if event.get("type") in events.TERMINAL:
                    break
        finally:
            await pubsub.unsubscribe(events.channel(job_id))
            await pubsub.aclose()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/runs", response_class=HTMLResponse)
async def runs_browser(request: Request):
    """Browse every individual run saved under results/ (read straight from disk)."""
    rows = [
        {"region": e.region, "combo": e.combo, "network": f"{e.region}/{e.combo}",
         "model": e.model, "strategy": e.strategy, "coverage": e.coverage,
         "seed": e.seed, "peak": e.peak, "label": e.label, "has_nodes": e.has_nodes}
        for e in scan_runs()
    ]
    rows.sort(key=lambda r: r["peak"], reverse=True)
    return templates.TemplateResponse(request, "runs.html", {
        "rows": rows,
        "regions": sorted({r["network"] for r in rows}),
        "models": sorted({r["model"] for r in rows}),
        "strategies": sorted({r["strategy"] for r in rows}),
    })


@app.get("/run/{region}/{combo}/{label}", response_class=HTMLResponse)
async def run_view(request: Request, region: str, combo: str, label: str):
    if not run_json(region, combo, label).exists():
        return HTMLResponse("Unknown run", status_code=404)
    ctx = results_context(region, combo, label)
    title = (f"{region}/{combo} · {ctx['config']['model']['name'].upper()} · "
             f"{ctx['config']['strategy']['name']}")
    return templates.TemplateResponse(request, "results.html", {
        "region": region, "combo": combo, "label": label, "title": title, **ctx})


@app.post("/run/{region}/{combo}/{label}/continue")
async def run_continue(request: Request, region: str, combo: str, label: str,
                       extra_days: int = Form(...)):
    path = run_json(region, combo, label)
    if not path.exists():
        return HTMLResponse("Unknown run", status_code=404)
    record = json.loads(path.read_text())
    elapsed = int(record["config"]["sim"]["horizon"])
    title = f"{region}/{combo} · {label} · +{extra_days}d"
    new_id = jobs.create_job("continue", title, region=region, combo=combo, label=label,
                             extra_days=extra_days)
    await app.state.arq.enqueue_job(
        "continue_simulation", new_id, region, combo, label, extra_days, elapsed
    )
    return RedirectResponse(f"/sim/{new_id}", status_code=303)


@app.get("/compare", response_class=HTMLResponse)
async def compare(request: Request):
    # one page, two tabs: overlay chosen runs (?r=region/combo/label) + aggregates
    run_ids = request.query_params.getlist("r")
    ctx = comparison_context(run_ids)
    ctx["agg"] = aggregate_context()
    return templates.TemplateResponse(request, "compare.html", ctx)


@app.get("/study", response_class=HTMLResponse)
async def study_form(request: Request):
    return templates.TemplateResponse(request, "study.html", {
        "networks": available_networks(),
        "models": [m.value for m in ModelName],
        "strategies": [s.value for s in StrategyName],
    })


@app.post("/study/run")
async def study_run(request: Request):
    form = await request.form()
    cfg = build_study_config(form)
    # validate the generated grid before committing to a job
    try:
        exp = ExperimentConfig.model_validate(cfg)
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(request, "study.html", {
            "networks": available_networks(),
            "models": [m.value for m in ModelName],
            "strategies": [s.value for s in StrategyName],
            "error": f"Invalid configuration: {exc}",
        }, status_code=400)

    for net in cfg["networks"]:
        if not graph_is_built(net["region"], net["layers"]):
            return templates.TemplateResponse(request, "study.html", {
                "networks": available_networks(),
                "models": [m.value for m in ModelName],
                "strategies": [s.value for s in StrategyName],
                "error": f"Network '{net['region']} / {combo_name(net['layers'])}' is not "
                         f"built — build it on the Data page first.",
            }, status_code=400)

    n_runs = len(exp.expand())
    maps = form.get("maps") == "on"

    studies = ensure_dir(RESULTS / "studies")
    region = cfg["networks"][0]["region"]
    n_nets = len(cfg["networks"])
    nets_label = f"{n_nets} networks" if n_nets > 1 else combo_name(cfg["networks"][0]["layers"])
    title = f"{region} · {nets_label} · {n_runs} runs"
    job_id = jobs.create_job("study", title)
    config_path = studies / f"{job_id}.yaml"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    await app.state.arq.enqueue_job("run_study", job_id, str(config_path), maps)
    return RedirectResponse(f"/study/{job_id}", status_code=303)


@app.get("/study/{job_id}", response_class=HTMLResponse)
async def study_monitor(request: Request, job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        return HTMLResponse("Unknown job", status_code=404)
    return templates.TemplateResponse(request, "study_monitor.html", {"job": job})


@app.get("/data", response_class=HTMLResponse)
async def data_page(request: Request):
    return templates.TemplateResponse(request, "data.html", _data_ctx())


@app.get("/data/status", response_class=HTMLResponse)
async def data_status_fragment(request: Request):
    # polled by htmx so action buttons reflect job progress without a full reload
    return templates.TemplateResponse(request, "_data_status.html", _data_ctx())


@app.post("/data/run")
async def data_run(request: Request):
    form = await request.form()
    action = form.get("action", "")
    region = form.get("region", "")
    layers = form.getlist("layers")
    titles = {
        "retrieve": "retrieve all sources",
        "netgen_all": "build all networks",
        "netgen_one": f"build {region}/{'+'.join(layers) or 'air'}",
        "aggregate": "aggregate (collect + structure)",
    }
    if action not in titles:
        return HTMLResponse("Unknown action", status_code=400)
    job_id = jobs.create_job("data", titles[action])
    await app.state.arq.enqueue_job("run_data_task", job_id, action, region or None, layers or None)
    return RedirectResponse("/data", status_code=303)


def _data_ctx() -> dict:
    return {**data_status(),
            "jobs": [j for j in jobs.list_jobs(limit=20) if j["kind"] == "data"]}


# --- Gephi exports (generated on demand) ------------------------------------

@app.get("/run/{region}/{combo}/{label}/gexf/{which}")
async def gexf(region: str, combo: str, label: str, which: str):
    path = run_json(region, combo, label)
    if not path.exists():
        return HTMLResponse("No artifacts for this run", status_code=404)
    record = json.loads(path.read_text())
    graph = read_graphml(record["config"]["network"].get("graph_path")
                         or processed_graph(region, combo))
    if which == "network":
        path = ensure_parent(network_gexf(region, combo))
        build_network_gexf(graph, path)
        return FileResponse(path, filename=f"{region}-{combo}.gexf")
    if which == "run":
        import pandas as pd
        node_ts = pd.read_parquet(run_node_timeseries(region, combo, label))
        path = ensure_parent(run_gexf(region, combo, label))
        build_run_gexf(graph, node_ts, path)
        return FileResponse(path, filename=f"{label}-outbreak.gexf")
    return HTMLResponse("Unknown export", status_code=404)

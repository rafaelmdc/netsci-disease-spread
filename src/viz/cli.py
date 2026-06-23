"""`netsci viz ...` — render interactive HTML for a run."""

from __future__ import annotations

import json

import pandas as pd
import typer

from src.config import load_run_config
from src.netgen.graph_io import read_graphml
from src.paths import (
    combo_name,
    ensure_dir,
    figures_dir,
    processed_graph,
    run_json,
    run_timeseries,
)
from src.viz.curves_html import curves_to_html
from src.viz.network_html import network_to_html

app = typer.Typer(help="Shared module: interactive HTML visualization.")


@app.command()
def build(config: str = typer.Option(..., help="path to the run YAML config")) -> None:
    """Render network + curves + a dashboard index for one run."""
    cfg = load_run_config(config)
    combo = combo_name([layer.value for layer in cfg.network.layers])
    region = cfg.network.region

    graph_path = cfg.network.graph_path or processed_graph(region, combo)
    graph = read_graphml(graph_path)

    record = json.loads(run_json(region, combo, cfg.run_id).read_text())
    targets = record.get("targets", [])
    ts = pd.read_parquet(run_timeseries(region, combo, cfg.run_id))

    out_dir = ensure_dir(figures_dir(region, combo))
    net_html = network_to_html(graph, out_dir / "network.html", targets=targets)
    cur_html = curves_to_html(ts, out_dir / f"{cfg.run_id}_curves.html",
                              title=f"{cfg.model.name.value.upper()} / {cfg.strategy.name.value}")

    index = out_dir / "index.html"
    index.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<h1>{region} / {combo} / {cfg.run_id}</h1>"
        f"<p>model={cfg.model.name.value} strategy={cfg.strategy.name.value}</p>"
        f"<ul>"
        f"<li><a href='{net_html.name}'>interactive network</a></li>"
        f"<li><a href='{cur_html.name}'>epidemic curves</a></li>"
        f"</ul>"
    )
    typer.echo(f"wrote {net_html}\n      {cur_html}\n      {index}")

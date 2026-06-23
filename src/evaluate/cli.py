"""`netsci evaluate ...` — run one experiment, write results."""

from __future__ import annotations

import json
import platform

import pandas as pd
import typer

from src.config import RunConfig, load_run_config
from src.evaluate.engine import simulate
from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import combo_name, ensure_parent, processed_graph, run_json, run_timeseries

app = typer.Typer(help="Module 3: evaluation.")


def _resolve_graph_path(cfg: RunConfig):
    if cfg.network.graph_path:
        return cfg.network.graph_path
    combo = combo_name([layer.value for layer in cfg.network.layers])
    return processed_graph(cfg.network.region, combo)


@app.command()
def run(config: str = typer.Option(..., help="path to a run YAML config")) -> None:
    """Load a config, simulate, and write <run_id>.json + timeseries.parquet."""
    cfg = load_run_config(config)
    graph_path = _resolve_graph_path(cfg)
    graph = read_graphml(graph_path)

    result = simulate(graph, cfg)
    combo = combo_name([layer.value for layer in cfg.network.layers])

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

    typer.echo(f"run_id={cfg.run_id}  peak_infected={result.summary['peak_infected']:.0f}")
    typer.echo(f"  -> {out_json}")

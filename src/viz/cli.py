"""`netsci viz ...` — render interactive, navigable HTML for runs & networks.

Figures are written **inside the run/network folder** they describe (see
docs/VISUALIZATION.md), so a results folder is self-contained and navigable.
"""

from __future__ import annotations

import json

import pandas as pd
import typer

from src.config import load_run_config
from src.evaluate.runner import run_and_save
from src.netgen.graph_io import read_graphml
from src.paths import (
    RESULTS,
    combo_name,
    network_figure,
    processed_graph,
    results_figure,
    run_figure,
    run_json,
    run_node_timeseries,
    run_timeseries,
)
from src.viz.compare_html import region_spectrum_html, strategy_comparison_html
from src.viz.curves_html import curves_to_html
from src.viz.network_html import network_to_html
from src.viz.spread_html import spread_to_html

app = typer.Typer(help="Shared module: interactive HTML visualization.")


def _run_subtitle(cfg, record: dict) -> str:
    p = cfg.model.params
    rates = f"β={p.beta}, γ={p.gamma}" + (f", σ={p.sigma}" if p.sigma else "")
    return (
        f"strategy: <b>{cfg.strategy.name.value}</b> "
        f"({cfg.strategy.budget} cities, {cfg.strategy.coverage:.0%} coverage, "
        f"{cfg.strategy.efficacy:.0%} efficacy)  ·  rates: {rates}  ·  "
        f"{cfg.sim.horizon}-day horizon, travel rate τ={cfg.sim.tau}, seed {cfg.sim.seed}  ·  "
        f"network: {int(record['network']['n_nodes'])} nodes / "
        f"{int(record['network']['n_edges'])} edges  ·  "
        f"peak active infections: {record['summary']['peak_infected']:,.0f}"
    )


@app.command()
def build(config: str = typer.Option(..., help="path to the run YAML config")) -> None:
    """Render network + curves + a navigable index for one run (co-located)."""
    cfg = load_run_config(config)
    combo = combo_name([layer.value for layer in cfg.network.layers])
    region = cfg.network.region

    graph_path = cfg.network.graph_path or processed_graph(region, combo)
    graph = read_graphml(graph_path)

    record = json.loads(run_json(region, combo, cfg.label).read_text())
    targets = record.get("targets", [])
    ts = pd.read_parquet(run_timeseries(region, combo, cfg.label))

    # network view is a property of the network -> network folder (shared by runs)
    net_path = network_figure(region, combo, "network.html")
    net_html = network_to_html(graph, net_path, targets=targets)
    title = f"{cfg.model.name.value.upper()} on {region} / {combo}"
    subtitle = _run_subtitle(cfg, record)
    cur_html = curves_to_html(ts, run_figure(region, combo, cfg.label, "curves.html"),
                              title=title, subtitle=subtitle)

    links = ["<li><a href='curves.html'>epidemic curves</a></li>",
             "<li><a href='../network.html'>interactive network</a></li>"]
    spread = run_node_timeseries(region, combo, cfg.label)
    if spread.exists():
        links.insert(0, "<li><a href='spread_geo.html'>animated outbreak map</a></li>")
    index = run_figure(region, combo, cfg.label, "index.html")
    index.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<h1>{region} / {combo} / {cfg.label}</h1>"
        f"<p>model={cfg.model.name.value} · strategy={cfg.strategy.name.value} · "
        f"peak={record['summary']['peak_infected']:,.0f}</p>"
        f"<ul>{''.join(links)}</ul>"
    )
    typer.echo(f"wrote {cur_html}\n      {net_html}\n      {index}")


@app.command()
def animate(
    config: str = typer.Option(..., help="path to the run YAML config"),
    force: bool = typer.Option(False, help="re-simulate even if node history exists"),
) -> None:
    """Render the animated geographic outbreak map for one run.

    Needs per-node history; if it isn't on disk yet (or --force), the run is
    (re)simulated with node recording first, then the map is written next to it.
    """
    cfg = load_run_config(config)
    combo = combo_name([layer.value for layer in cfg.network.layers])
    region = cfg.network.region

    node_ts_path = run_node_timeseries(region, combo, cfg.label)
    if force or not node_ts_path.exists():
        typer.echo("simulating with per-node recording ...")
        run_and_save(cfg, record_nodes=True)

    node_ts = pd.read_parquet(node_ts_path)
    record = json.loads(run_json(region, combo, cfg.label).read_text())
    title = f"{cfg.model.name.value.upper()} outbreak — {region} / {combo}"
    out = spread_to_html(node_ts, run_figure(region, combo, cfg.label, "spread_geo.html"),
                         title=title, subtitle=_run_subtitle(cfg, record))
    typer.echo(f"wrote {out}")


@app.command()
def compare(
    summary: str = typer.Option(str(RESULTS / "summary.parquet"), help="collected summary table"),
) -> None:
    """Render the cross-strategy / cross-model comparison plot."""
    df = pd.read_parquet(summary)
    out = strategy_comparison_html(df, results_figure("strategy_comparison.html"))
    typer.echo(f"wrote {out}")


@app.command()
def spectrum(
    structure: str = typer.Option(str(RESULTS / "structure.parquet"), help="structure table"),
) -> None:
    """Render the cross-region degree-betweenness spectrum plot."""
    df = pd.read_parquet(structure)
    out = region_spectrum_html(df, results_figure("region_spectrum.html"))
    typer.echo(f"wrote {out}")


@app.command()
def site() -> None:
    """(Re)build the navigable static site: three levels of index.html plus
    each run's curves/map and each network's structure/strategy panels — all
    co-located under results/. Reads on-disk runs; never simulates."""
    from src.viz.site import build_site

    tally = build_site()
    typer.echo(
        f"built site for {tally['runs']} runs across {tally['networks']} network(s) "
        f"→ open {results_figure('index.html')}"
    )

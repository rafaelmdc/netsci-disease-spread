"""`netsci evaluate ...` — run experiments, sweeps, and aggregation."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import typer

from src.config import ModelName, load_run_config
from src.evaluate.centrality import betweenness
from src.evaluate.operating_point import recommend, scan_tau
from src.evaluate.runner import run_and_save
from src.experiment import load_experiment_config
from src.netgen.graph_io import read_graphml
from src.paths import RESULTS, combo_name, processed_graph

app = typer.Typer(help="Module 3: evaluation.")


@app.command()
def run(config: str = typer.Option(..., help="path to a run YAML config")) -> None:
    """Load a config, simulate, and write <run_id>.json + timeseries.parquet."""
    record = run_and_save(load_run_config(config))
    typer.echo(
        f"run_id={record['run_id']}  peak_infected={record['summary']['peak_infected']:,.0f}"
    )


@app.command()
def sweep(
    config: str = typer.Option("experiment.yaml", help="path to the master experiment config"),
    workers: int = typer.Option(4, help="parallel worker threads"),
) -> None:
    """Expand the experiment config and run the whole grid, per network."""
    exp = load_experiment_config(config)
    groups = exp.grouped_by_network()
    total = sum(len(v) for v in groups.values())
    typer.echo(f"running {total} configs across {len(groups)} network(s) ...")
    for (region, combo), cfgs in groups.items():
        graph = read_graphml(processed_graph(region, combo))
        betweenness(graph)  # warm the cache once before threads share the graph
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda c, g=graph: run_and_save(c, g), cfgs))
        typer.echo(f"  {region}/{combo}: {len(cfgs)} runs -> results/{region}/{combo}/")


@app.command(name="operating-point")
def operating_point(
    region: str = "europe",
    layers: str = "air",
    model: str = "sir",
    horizon: int = 180,
    taus: str = "0.0002,0.0005,0.001,0.002,0.005,0.01",
) -> None:
    """Scan the travel rate to find an informative regime (peak reached, attack
    rate in band) — the principled stand-in for calibration."""
    graph = read_graphml(processed_graph(region, combo_name(layers.split(","))))
    tau_list = [float(t) for t in taus.split(",")]
    rows = scan_tau(graph, ModelName(model), tau_list, horizon, region=region)
    typer.echo(f"{model} on {region}/{layers}, horizon={horizon} days:")
    typer.echo(f"  {'tau':>8} {'attack':>8} {'peak_day':>9} {'peak?':>6} {'informative':>12}")
    for r in rows:
        typer.echo(
            f"  {r['tau']:>8.4f} {r['attack_rate']:>7.1%} {r['peak_day']:>9} "
            f"{str(r['peak_reached']):>6} {str(r['informative']):>12}"
        )
    best = recommend(rows)
    if best:
        typer.echo(f"recommended tau={best['tau']} (attack {best['attack_rate']:.0%}, "
                   f"peak day {best['peak_day']})")
    else:
        typer.echo("no informative tau in range — try a longer horizon or wider tau range")


@app.command()
def collect(out: str = typer.Option("results/summary.parquet")) -> None:
    """Aggregate every run's JSON into one tidy table for comparison."""
    rows = []
    for path in sorted(RESULTS.rglob("*.json")):
        d = json.loads(path.read_text())
        cfg, summ, struct = d["config"], d["summary"], d["structural"]
        rows.append(
            {
                "region": cfg["network"]["region"],
                "combo": combo_name([layer for layer in cfg["network"]["layers"]]),
                "run_id": d["run_id"],
                "model": cfg["model"]["name"],
                "beta": cfg["model"]["params"]["beta"],
                "gamma": cfg["model"]["params"]["gamma"],
                "strategy": cfg["strategy"]["name"],
                "budget": cfg["strategy"]["budget"],
                "coverage": cfg["strategy"]["coverage"],
                "efficacy": cfg["strategy"]["efficacy"],
                "tau": cfg["sim"]["tau"],
                "horizon": cfg["sim"]["horizon"],
                "seed": cfg["sim"]["seed"],
                "spearman_deg_btw": struct["spearman_deg_btw"],
                "n_anomalous": len(struct["anomalous_gateways"]),
                **{k: summ[k] for k in summ},
            }
        )
    if not rows:
        typer.echo("no results found under results/")
        raise typer.Exit(1)
    df = pd.DataFrame(rows)
    out_path = RESULTS / "summary.parquet" if out == "results/summary.parquet" else out
    df.to_parquet(out_path)
    df.to_csv(str(out_path).replace(".parquet", ".csv"), index=False)
    typer.echo(f"collected {len(df)} runs -> {out_path}")

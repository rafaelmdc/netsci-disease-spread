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
from src.paths import RESULTS, combo_name, ensure_parent, processed_graph

app = typer.Typer(help="Module 3: evaluation.")


@app.command()
def run(config: str = typer.Option(..., help="path to a run YAML config")) -> None:
    """Load a config, simulate, and write <run_id>.json + timeseries.parquet."""
    record = run_and_save(load_run_config(config))
    typer.echo(
        f"{record['label']}  peak_infected={record['summary']['peak_infected']:,.0f}"
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
def structure(
    regions: str = "europe,americas,asia,africa,oceania",
    layers: str = "air",
) -> None:
    """Cross-region structural comparison: rho(degree, betweenness) and
    anomalous gateways per region — the novelty measurement, topology only."""
    from src.config import Layer, NetworkConfig
    from src.evaluate.metrics import characterize, degree_betweenness
    from src.netgen.build import build_network

    layer_list = [Layer(x) for x in layers.split(",")]
    rows = []
    for region in regions.split(","):
        graph = build_network(NetworkConfig(region=region, layers=layer_list))
        ch = characterize(graph)
        db = degree_betweenness(graph)
        rows.append(
            {
                "region": region,
                "n_nodes": int(ch["n_nodes"]),
                "mean_degree": round(ch["mean_degree"], 1),
                "k2_over_k": round(ch["k2_over_k"], 1),
                "spearman_deg_btw": round(db["spearman_deg_btw"], 3),
                "n_anomalous": len(db["anomalous_gateways"]),
                "anomalous_sample": ",".join(db["anomalous_gateways"][:6]),
            }
        )
    # Report a relative spectrum (no arbitrary cutoff): highest rho = most
    # degree/betweenness-correlated (US-like end), lowest = most anomalous.
    rows.sort(key=lambda r: r["spearman_deg_btw"], reverse=True)
    typer.echo("  region spectrum: correlated (US-like) -> anomalous (worldwide-like)")
    for r in rows:
        typer.echo(
            f"  {r['region']:10s} rho={r['spearman_deg_btw']:.3f}  "
            f"{r['n_anomalous']:>3} anomalous gateways"
        )
    df = pd.DataFrame(rows)
    out = RESULTS / "structure.parquet"
    ensure_parent(out)
    df.to_parquet(out)
    df.to_csv(str(out).replace(".parquet", ".csv"), index=False)
    typer.echo(f"wrote {out}")


@app.command()
def collect(out: str = typer.Option("results/summary.parquet")) -> None:
    """Aggregate every run's JSON into one tidy table for comparison."""
    rows = []
    for path in sorted(RESULTS.rglob("*.json")):
        d = json.loads(path.read_text())
        cfg, summ, struct = d["config"], d["summary"], d["structural"]
        rows.append(
            {
                "label": d.get("label", d["run_id"]),
                "region": cfg["network"]["region"],
                "combo": combo_name([layer for layer in cfg["network"]["layers"]]),
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
                "spearman_deg_btw": round(struct["spearman_deg_btw"], 3),
                "n_anomalous": len(struct["anomalous_gateways"]),
                # round counts to whole people for readability
                **{k: round(v) for k, v in summ.items()},
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

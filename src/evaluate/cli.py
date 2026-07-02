"""`netsci evaluate ...` — run experiments, sweeps, and aggregation."""

from __future__ import annotations

import pandas as pd
import typer

from src.config import ModelName, load_run_config
from src.evaluate.operating_point import recommend, scan_tau
from src.evaluate.runner import run_and_save
from src.experiment import load_experiment_config
from src.netgen.graph_io import read_graphml
from src.paths import RESULTS, combo_name, ensure_parent, processed_graph

app = typer.Typer(help="Module 3: evaluation.")


@app.command()
def run(config: str = typer.Option(..., help="path to a run YAML config")) -> None:
    """Load a config, simulate, and write <label>/summary.json + timeseries.parquet."""
    record = run_and_save(load_run_config(config))
    typer.echo(
        f"{record['label']}  peak_infected={record['summary']['peak_infected']:,.0f}"
    )


@app.command()
def sweep(
    config: str = typer.Option("experiment.yaml", help="path to the master experiment config"),
    workers: int = typer.Option(4, help="parallel worker threads"),
    maps: bool = typer.Option(
        False, "--maps", help="also record per-node history (node_timeseries.parquet) so the "
        "explorer can draw every run's animated map with no re-simulation (~2 GB for the full grid)"
    ),
) -> None:
    """Expand the experiment config and run the whole FACTORIAL grid, per network."""
    from src.evaluate.sweep import run_experiment

    run_experiment(load_experiment_config(config), workers=workers, maps=maps, echo=typer.echo)


@app.command()
def staged(
    config: str = typer.Option("experiment.yaml", help="path to the master experiment config"),
    workers: int = typer.Option(4, help="parallel worker threads"),
    maps: bool = typer.Option(
        False, "--maps", help="also record per-node history for the animated outbreak maps"
    ),
) -> None:
    """Run the staged ('greedy with re-check') protocol: spread -> vaccinate ->
    re-check, letting stage 2's results choose which strategy stage 3 verifies.
    The small, sequential alternative to the full factorial `sweep`."""
    from src.evaluate.staged import run_staged

    winners = run_staged(
        load_experiment_config(config), workers=workers, maps=maps, echo=typer.echo
    )
    summary = ", ".join(f"{d}->{w.value}" for d, w in winners.items())
    typer.echo(f"staged protocol complete - best defense per disease: {summary}")


@app.command()
def dose(
    config: str = typer.Option("experiment.yaml", help="path to the master experiment config"),
    workers: int = typer.Option(4, help="parallel worker threads"),
) -> None:
    """Run ONLY the dose-response stage (stage 4): sweep the already-chosen
    winning strategy's budget on the flagship. Reuses the winner from the last
    stage-2 results, so stages 1-3 are not re-simulated."""
    from src.evaluate.staged import run_dose

    winners = run_dose(load_experiment_config(config), workers=workers, echo=typer.echo)
    summary = ", ".join(f"{d}->{w.value}" for d, w in winners.items())
    typer.echo(f"dose-response complete for winners: {summary}")


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
def interdiction(
    config: str = typer.Option(..., help="run YAML config (use the flagship multilayer network)"),
    k: int = typer.Option(10, help="how many top airports to close in scenarios D1/D2"),
) -> None:
    """Air-interdiction experiment (scenarios A–D): close flight routes and see
    whether land+water still carry the outbreak. Writes interdiction.html into
    the network folder. Best run on europe/air+land+water."""
    from src.evaluate.interdiction import run_scenarios
    from src.paths import network_figure
    from src.viz.interdiction_html import interdiction_to_html

    cfg = load_run_config(config)
    combo = combo_name([layer.value for layer in cfg.network.layers])
    region = cfg.network.region
    graph = read_graphml(cfg.network.graph_path or processed_graph(region, combo))

    results = run_scenarios(graph, cfg, k=k)
    out = interdiction_to_html(
        results, network_figure(region, combo, "interdiction.html"),
        title=f"Air interdiction — {region} / {combo}",
    )
    # Persist the scenario curves so the static paper figure (F7) needs no re-sim.
    series = pd.DataFrame(
        [
            {"scenario": name, "day": day, "infectious": v, "region": region, "combo": combo}
            for name, r in results.items()
            for day, v in enumerate(r["infectious"])
        ]
    )
    series_path = network_figure(region, combo, "interdiction.parquet")
    series.to_parquet(series_path)
    for name, r in results.items():
        typer.echo(f"  {name:42s} peak={r['summary']['peak_infected']:,.0f}")
    typer.echo(f"wrote {out} and {series_path.name}")


@app.command()
def collect() -> None:
    """Aggregate every run's JSON into tidy tables (summary + strategy gap)."""
    from src.evaluate.aggregate import collect as collect_runs

    df = collect_runs(write=True)
    if df.empty:
        typer.echo("no results found under results/")
        raise typer.Exit(1)
    typer.echo(f"collected {len(df)} runs -> {RESULTS / 'summary.parquet'}")
    if (RESULTS / "strategy_gap.parquet").exists():
        typer.echo(f"wrote degree-vs-betweenness gap -> {RESULTS / 'strategy_gap.parquet'}")

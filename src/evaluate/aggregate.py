"""Aggregate run outputs into the study-wide tables the app and paper read.

Importable (no typer) so both the CLI and the Dash app can build them — the app
calls these on launch so it is genuinely one command end-to-end.

  - ``collect``        : every run's summary.json  -> results/summary.parquet
  - ``strategy_gap``   : degree- vs betweenness-targeting  -> strategy_gap.parquet
  - ``structure_table``: per built network ρ(deg,btw)+gateways -> structure.parquet
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pandas as pd

from src.evaluate.centrality import nb_leading_eigenvalue
from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import PROCESSED, RESULTS, combo_name, processed_graph


def ci95(x) -> float:
    """Half-width of the 95% confidence interval of the mean, across a seed
    ensemble. Returns 0.0 for a single sample (nothing to be uncertain about
    yet). Used everywhere we turn a set of per-seed values into mean +/- band."""
    a = np.asarray(x, dtype=float)
    a = a[~np.isnan(a)]
    n = a.size
    if n < 2:
        return 0.0
    return float(1.96 * a.std(ddof=1) / np.sqrt(n))


def collect(write: bool = True) -> pd.DataFrame:
    """Flatten every run's summary.json into one tidy table."""
    rows = []
    for path in sorted(RESULTS.rglob("summary.json")):
        try:
            d = json.loads(path.read_text())
            cfg, summ, struct = d["config"], d["summary"], d["structural"]
        except (KeyError, json.JSONDecodeError):
            continue
        rows.append(
            {
                "label": d.get("label", d.get("run_id")),
                "region": cfg["network"]["region"],
                "combo": combo_name(list(cfg["network"]["layers"])),
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
                **{k: round(v) for k, v in summ.items()},
            }
        )
    df = pd.DataFrame(rows)
    if write and not df.empty:
        _write(df, RESULTS / "summary.parquet")
        gap = strategy_gap(df)
        if gap is not None:
            _write(gap, RESULTS / "strategy_gap.parquet")
    return df


def strategy_gap(df: pd.DataFrame) -> pd.DataFrame | None:
    """Per network/model/coverage: peak under degree- vs betweenness-targeting and
    their gap, as a seed ensemble. The gap is computed *per seed* (degree and
    betweenness share the seed's initial-infection placement, so it is a paired
    comparison), then averaged, with a 95% CI. ``gap_rel_ci`` clear of zero means
    betweenness genuinely beats degree; a near-zero gap means the cheap degree
    strategy matches the expensive betweenness one (US-like)."""
    pair = df[df["strategy"].isin(["degree", "betweenness"])]
    if pair.empty:
        return None
    # per-seed pivot: one degree and one betweenness peak per seed.
    keys = ["region", "combo", "model", "coverage", "seed"]
    piv = (
        pair.groupby([*keys, "strategy"])["peak_infected"].mean().unstack("strategy")
    )
    if not {"degree", "betweenness"}.issubset(piv.columns):
        return None
    piv = piv.reset_index().rename(
        columns={"degree": "peak_degree", "betweenness": "peak_betweenness"}
    )
    piv["gap_abs"] = piv["peak_degree"] - piv["peak_betweenness"]
    piv["gap_rel"] = piv["gap_abs"] / piv["peak_degree"].where(piv["peak_degree"] > 0)
    # collapse the seed ensemble to mean +/- 95% CI per configuration.
    grp = piv.groupby(["region", "combo", "model", "coverage"])
    g = grp.agg(
        n_seeds=("gap_abs", "size"),
        peak_degree=("peak_degree", "mean"),
        peak_betweenness=("peak_betweenness", "mean"),
        gap_abs=("gap_abs", "mean"),
        gap_abs_ci=("gap_abs", ci95),
        gap_rel=("gap_rel", "mean"),
        gap_rel_ci=("gap_rel", ci95),
    ).reset_index()
    return g


def deaths_table(write: bool = True) -> pd.DataFrame:
    """Cumulative deaths for the lethal SEIQRD type, and deaths averted vs the
    same-seed control. The engine writes the ``D`` (dead) compartment into every
    run's ``timeseries.parquet`` but not into ``summary.json``, so we read the
    final ``D`` from the time series: no re-simulation. ``peak_infected`` hides
    case fatality (mu ~= 0.71 for the Ebola exemplar), so this is the metric that
    makes the lethal type's results meaningful (see RESEARCH-ROADMAP #4)."""
    rows = []
    for path in sorted(RESULTS.rglob("summary.json")):
        try:
            d = json.loads(path.read_text())
            cfg = d["config"]
        except (KeyError, json.JSONDecodeError):
            continue
        if cfg["model"]["name"] != "seiqrd":
            continue
        ts_path = path.parent / "timeseries.parquet"
        if not ts_path.exists():
            continue
        try:
            ts = pd.read_parquet(ts_path, columns=["D"])
        except (OSError, ValueError, KeyError):
            continue
        rows.append(
            {
                "region": cfg["network"]["region"],
                "combo": combo_name(list(cfg["network"]["layers"])),
                "strategy": cfg["strategy"]["name"],
                "budget": cfg["strategy"]["budget"],
                "coverage": cfg["strategy"]["coverage"],
                "seed": cfg["sim"]["seed"],
                "deaths": float(ts["D"].iloc[-1]),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # deaths averted = control deaths - strategy deaths, paired on seed (control
    # shares each seed's initial placement, so it is the right baseline).
    ctrl = (
        df[df["strategy"] == "control"]
        .groupby(["region", "combo", "seed"])["deaths"]
        .mean()
        .rename("deaths_control")
        .reset_index()
    )
    out = df[df["strategy"] != "control"].merge(
        ctrl, on=["region", "combo", "seed"], how="left"
    )
    out["deaths_averted"] = out["deaths_control"] - out["deaths"]
    if write:
        _write(out, RESULTS / "deaths.parquet")
    return out


def equity_table(
    region: str = "europe",
    combo: str = "air+land+water",
    budget: int = 15,
    write: bool = True,
) -> pd.DataFrame:
    """Geographic concentration of each strategy's vaccinated set: across how many
    countries the chosen cities spread, and how concentrated they are (Gini of the
    per-country counts, and the single most-targeted country's share). A strategy
    that is very effective but concentrates protection in a few countries poses an
    efficiency/equity tension, and connects to the peripheral gateways this study
    flags (see RESEARCH-ROADMAP #5). Deterministic per graph (no sweep needed)."""
    from src.config import StrategyConfig, StrategyName
    from src.evaluate.strategies import select_targets

    graph = read_graphml(processed_graph(region, combo))
    rng = np.random.default_rng(0)
    order = [
        "random", "degree", "betweenness", "subgraph",
        "collective_influence", "nonbacktracking",
    ]
    rows = []
    for name in order:
        try:
            picks = select_targets(
                graph, StrategyConfig(name=StrategyName(name), budget=budget), rng
            )
        except (NotImplementedError, ValueError):
            continue
        if not picks:
            continue
        counts = Counter(str(graph.nodes[n].get("country", "?")) for n in picks)
        vals = list(counts.values())
        rows.append(
            {
                "region": region,
                "combo": combo,
                "strategy": name,
                "budget": budget,
                "n_cities": len(picks),
                "n_countries": len(counts),
                "top_country": max(counts, key=counts.get),
                "top_country_share": max(vals) / len(picks),
                "gini": _gini(vals),
            }
        )
    df = pd.DataFrame(rows)
    if write and not df.empty:
        _write(df, RESULTS / "equity.parquet")
    return df


def _gini(values: list[float]) -> float:
    """Gini coefficient of a list of counts (0 = perfectly even, ->1 = all in
    one country). Defined as 0 for an empty or all-zero input."""
    a = np.sort(np.asarray(values, dtype=float))
    n = a.size
    total = a.sum()
    if n == 0 or total == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2.0 * np.sum(idx * a)) / (n * total) - (n + 1) / n)


def structure_table(write: bool = True) -> pd.DataFrame:
    """ρ(degree, betweenness) + anomalous gateways for every *built* network
    (read from data/processed, so it needs no re-simulation)."""
    rows = []
    for graph_path in sorted(PROCESSED.glob("*/*.graphml")):
        region, combo = graph_path.parent.name, graph_path.stem
        graph = read_graphml(graph_path)
        ch = characterize(graph)
        db = degree_betweenness(graph)
        # largest non-backtracking eigenvalue; its reciprocal is the analytic
        # SIR / bond-percolation epidemic threshold (see RESEARCH-ROADMAP #3).
        nb = nb_leading_eigenvalue(graph)
        rows.append(
            {
                "region": region,
                "combo": combo,
                "n_nodes": int(ch["n_nodes"]),
                "n_edges": int(ch["n_edges"]),
                "density": round(ch["density"], 4),
                "mean_degree": round(ch["mean_degree"], 1),
                "k2_over_k": round(ch["k2_over_k"], 1),
                "assortativity": round(ch["assortativity"], 3),
                "clustering": round(ch["clustering"], 3),
                "avg_path_length": round(ch["avg_path_length"], 2),
                "diameter": round(ch["diameter"], 0),
                "modularity": round(ch["modularity"], 3),
                "giant_frac": round(ch["giant_frac"], 3),
                "nb_eigenvalue": round(nb, 2),
                "epi_threshold": round(1.0 / nb, 4) if nb and nb == nb and nb > 0 else float("nan"),
                "spearman_deg_btw": round(db["spearman_deg_btw"], 3),
                "n_anomalous": len(db["anomalous_gateways"]),
                "anomalous_sample": ", ".join(
                    str(graph.nodes[n].get("name", n)) for n in db["anomalous_gateways"][:6]
                ),
            }
        )
    df = pd.DataFrame(rows)
    if write and not df.empty:
        _write(df, RESULTS / "structure.parquet")
    return df


def _write(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    df.to_csv(str(path).replace(".parquet", ".csv"), index=False)

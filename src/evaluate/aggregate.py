"""Aggregate run outputs into the study-wide tables the app and paper read.

Importable (no typer) so both the CLI and the Dash app can build them — the app
calls these on launch so it is genuinely one command end-to-end.

  - ``collect``        : every run's summary.json  -> results/summary.parquet
  - ``strategy_gap``   : degree- vs betweenness-targeting  -> strategy_gap.parquet
  - ``structure_table``: per built network ρ(deg,btw)+gateways -> structure.parquet
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import PROCESSED, RESULTS, combo_name


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


def structure_table(write: bool = True) -> pd.DataFrame:
    """ρ(degree, betweenness) + anomalous gateways for every *built* network
    (read from data/processed, so it needs no re-simulation)."""
    rows = []
    for graph_path in sorted(PROCESSED.glob("*/*.graphml")):
        region, combo = graph_path.parent.name, graph_path.stem
        graph = read_graphml(graph_path)
        ch = characterize(graph)
        db = degree_betweenness(graph)
        rows.append(
            {
                "region": region,
                "combo": combo,
                "n_nodes": int(ch["n_nodes"]),
                "mean_degree": round(ch["mean_degree"], 1),
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

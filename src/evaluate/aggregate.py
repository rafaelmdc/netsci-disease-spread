"""Aggregate run outputs into the study-wide tables the app and paper read.

Importable (no typer) so both the CLI and the Dash app can build them — the app
calls these on launch so it is genuinely one command end-to-end.

  - ``collect``        : every run's summary.json  -> results/summary.parquet
  - ``strategy_gap``   : degree- vs betweenness-targeting  -> strategy_gap.parquet
  - ``structure_table``: per built network ρ(deg,btw)+gateways -> structure.parquet
"""

from __future__ import annotations

import json

import pandas as pd

from src.evaluate.metrics import characterize, degree_betweenness
from src.netgen.graph_io import read_graphml
from src.paths import PROCESSED, RESULTS, combo_name


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
    """Per network/model/coverage (avg over seeds): peak under degree- vs
    betweenness-targeting and their gap. Near-zero gap => the cheap degree
    strategy matches the expensive betweenness one (US-like)."""
    pair = df[df["strategy"].isin(["degree", "betweenness"])]
    if pair.empty:
        return None
    piv = (
        pair.groupby(["region", "combo", "model", "coverage", "strategy"])["peak_infected"]
        .mean()
        .unstack("strategy")
    )
    if not {"degree", "betweenness"}.issubset(piv.columns):
        return None
    g = piv.reset_index().rename(
        columns={"degree": "peak_degree", "betweenness": "peak_betweenness"}
    )
    g["gap_abs"] = g["peak_degree"] - g["peak_betweenness"]
    g["gap_rel"] = g["gap_abs"] / g["peak_degree"].where(g["peak_degree"] > 0)
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

"""Render the existing Plotly figure builders as embeddable HTML fragments.

We reuse `src.viz`'s figure functions verbatim (the science/plots are correct);
the dashboard only swaps the shell. Plotly.js is loaded once by the page, so
fragments are emitted with ``include_plotlyjs=False``.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go

from src.netgen.graph_io import read_graphml
from src.paths import RESULTS, run_json, run_timeseries
from src.viz.catalog import RunEntry
from src.viz.compare_html import region_spectrum_figure, strategy_comparison_figure
from src.viz.curves_html import curves_figure
from src.viz.spread_html import spread_figure
from src.viz.structure_html import structure_figure

_PLOTLY_CFG = {"displaylogo": False, "responsive": True}


def _div(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config=_PLOTLY_CFG)


def _entry(region: str, combo: str, label: str) -> RunEntry:
    record = json.loads(run_json(region, combo, label).read_text())
    return RunEntry(
        label=label, region=region, combo=combo,
        model=record["config"]["model"]["name"],
        strategy=record["config"]["strategy"]["name"],
        coverage=float(record["config"]["strategy"]["coverage"]),
        seed=int(record["config"]["sim"]["seed"]),
        peak=float(record["summary"].get("peak_infected", 0.0)),
        summary_path=run_json(region, combo, label),
    )


def results_context(region: str, combo: str, label: str) -> dict:
    """Everything the results template needs: record + rendered figure divs."""
    record = json.loads(run_json(region, combo, label).read_text())
    entry = _entry(region, combo, label)

    ts = pd.read_parquet(run_timeseries(region, combo, label))
    curves = _div(curves_figure(ts, title="Epidemic curves"))

    spread = None
    if entry.has_nodes:
        node_ts = pd.read_parquet(entry.node_timeseries_path)
        spread = _div(spread_figure(node_ts, title="Outbreak spread"))

    structure = None
    try:
        graph = read_graphml(record["config"]["network"].get("graph_path")
                             or _graph_path(record))
        structure = _div(structure_figure(graph))
    except (FileNotFoundError, KeyError):
        structure = None

    return {
        "record": record,
        "summary": record["summary"],
        "config": record["config"],
        "curves_div": curves,
        "spread_div": spread,
        "structure_div": structure,
        "has_state": (entry.run_dir / "state.npz").exists(),
        "lineage": record.get("lineage", {}),
    }


def _graph_path(record: dict):
    from src.paths import combo_name, processed_graph
    net = record["config"]["network"]
    return processed_graph(net["region"], combo_name(list(net["layers"])))


_COMPS = ["S", "E", "I", "Q", "R", "V"]


def _mark(stats: list[dict]) -> None:
    """Tag the min/max cell per numeric column so the table can highlight them."""
    if len(stats) < 2:
        return
    for f in ("peak", "peak_day", "attack", "vaccinated"):
        vals = [(i, s[f]) for i, s in enumerate(stats) if s.get(f) is not None]
        if len(vals) < 2:
            continue
        hi = max(vals, key=lambda t: t[1])[0]
        lo = min(vals, key=lambda t: t[1])[0]
        if hi == lo:
            continue
        stats[hi].setdefault("mark", {})[f] = "hi"
        stats[lo].setdefault("mark", {})[f] = "lo"


def comparison_context(run_ids: list[str]) -> dict:
    """Build everything the Compare page needs to overlay N chosen runs.

    Each id is ``"<region>/<combo>/<label>"`` (none of those contain a slash);
    reads each run's timeseries + summary straight from disk. The curves are
    handed to the browser as raw series so the metric / normalisation can be
    switched client-side without a round-trip."""
    runs: list[dict] = []
    for rid in run_ids:
        parts = rid.split("/")
        if len(parts) != 3:
            continue
        region, combo, label = parts
        jpath = run_json(region, combo, label)
        if not jpath.exists():
            continue
        record = json.loads(jpath.read_text())
        cfg, summ = record["config"], record["summary"]
        ts = pd.read_parquet(run_timeseries(region, combo, label))
        comps = {c: [round(float(x), 2) for x in ts[c]] for c in _COMPS if c in ts.columns}
        runs.append({
            "region": region, "combo": combo, "label": label,
            "descriptor": f"{region}/{combo} · {cfg['model']['name'].upper()} · "
                          f"{cfg['strategy']['name']} · seed {cfg['sim']['seed']}",
            "comps": comps, "pop": round(float(summ.get("total_population") or 0), 2),
            "summary": summ, "config": cfg,
        })

    stats = []
    for r in runs:
        s = r["summary"]
        pop = s.get("total_population") or 0
        stats.append({
            "region": r["region"], "combo": r["combo"], "label": r["label"],
            "model": r["config"]["model"]["name"], "strategy": r["config"]["strategy"]["name"],
            "peak": s.get("peak_infected", 0.0),
            "peak_day": int(s.get("time_to_peak", 0)),
            "attack": (s.get("final_recovered", 0.0) / pop) if pop else None,
            "vaccinated": s.get("vaccinated", 0.0),
        })
    _mark(stats)

    metrics = [c for c in _COMPS if any(c in r["comps"] for r in runs)]
    chart_data = [{"name": r["descriptor"], "comps": r["comps"], "pop": r["pop"]} for r in runs]
    return {"n": len(runs), "chart_data": chart_data, "metrics": metrics, "stats": stats}


def aggregate_context() -> dict:
    """Study-level views: strategy bars, region spectrum, interdiction.

    Reads only the on-disk aggregate tables (`netsci evaluate collect` +
    `structure`) and pre-generated interdiction HTML — never simulates."""
    strategy_div = spectrum_div = None

    summary_path = RESULTS / "summary.parquet"
    if summary_path.exists():
        summary = pd.read_parquet(summary_path)
        if not summary.empty:
            strategy_div = _div(strategy_comparison_figure(summary))

    structure_path = RESULTS / "structure.parquet"
    if structure_path.exists():
        structure = pd.read_parquet(structure_path)
        if not structure.empty:
            spectrum_div = _div(region_spectrum_figure(structure))

    # interdiction HTML is generated by `netsci evaluate interdiction`; embed it.
    interdiction = [
        {"network": f"{p.parent.parent.name} / {p.parent.name}",
         "url": "/files/" + str(p.relative_to(RESULTS))}
        for p in sorted(RESULTS.rglob("interdiction.html"))
    ]

    return {
        "strategy_div": strategy_div,
        "spectrum_div": spectrum_div,
        "interdiction": interdiction,
        "has_any": bool(strategy_div or spectrum_div or interdiction),
    }

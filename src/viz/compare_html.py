"""Cross-experiment comparison plots from the collected summary table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.paths import ensure_parent
from src.viz.assets import plotlyjs_ref


def strategy_comparison_figure(summary: pd.DataFrame) -> go.Figure:
    """Grouped bars: mean peak infections per model, per strategy.

    Averaged over seeds; non-control strategies shown at high coverage so the
    comparison is like-for-like. Lower bars = better containment.
    """
    hi = summary["coverage"].max()
    df = summary[(summary["strategy"] == "control") | (summary["coverage"] == hi)]
    agg = (
        df.groupby(["model", "strategy"], as_index=False)
        .agg(peak_infected=("peak_infected", "mean"), peak_std=("peak_infected", "std"))
        .sort_values("model")
    )
    agg["peak_std"] = agg["peak_std"].fillna(0.0)  # single-seed groups have no spread
    fig = px.bar(
        agg,
        x="model",
        y="peak_infected",
        color="strategy",
        barmode="group",
        error_y="peak_std",
        title="Peak active infections by model and vaccination strategy",
        labels={"peak_infected": "mean peak infected (over seeds)", "model": "model"},
        template="plotly_white",
    )
    # error bars (±1 std over seeds) are opt-in — hidden until toggled on
    fig.update_traces(error_y_visible=False)
    fig.add_annotation(
        text="Lower is better; targeted strategies should sit below control/random.",
        xref="paper", yref="paper", x=0, y=1.08, showarrow=False, font=dict(size=11),
    )
    return fig


def strategy_comparison_html(summary: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    ensure_parent(path)
    strategy_comparison_figure(summary).write_html(str(path), include_plotlyjs=plotlyjs_ref(path))
    return path


def strategy_panel_figure(summary: pd.DataFrame, title: str = "") -> go.Figure:
    """One network's deliverable panel: a facet per disease model, bars over
    strategies, split by coverage. Averaged over seeds; lower = better
    containment. This is the cell-grid read across models for a fixed network.
    """
    df = summary.copy()
    df["coverage_label"] = df.apply(
        lambda r: "control" if r["strategy"] == "control" else f"{r['coverage']:.0%} coverage",
        axis=1,
    )
    agg = (
        df.groupby(["model", "strategy", "coverage_label"], as_index=False)["peak_infected"]
        .mean()
    )
    fig = px.bar(
        agg.sort_values("model"),
        x="strategy", y="peak_infected", color="coverage_label",
        facet_col="model", facet_col_wrap=2, barmode="group",
        title=title or "Peak infections by strategy, per disease model",
        labels={"peak_infected": "mean peak infected", "coverage_label": "coverage"},
        template="plotly_white",
    )
    fig.update_layout(height=760)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1].upper()))
    return fig


def strategy_panel_html(summary: pd.DataFrame, path: str | Path, title: str = "") -> Path:
    path = Path(path)
    ensure_parent(path)
    strategy_panel_figure(summary, title=title).write_html(
        str(path), include_plotlyjs=plotlyjs_ref(path)
    )
    return path


def region_spectrum_figure(structure: pd.DataFrame) -> go.Figure:
    """Bar chart of rho(degree, betweenness) per region — the centrality
    spectrum from correlated (US-like) to anomalous (worldwide-like)."""
    df = structure.sort_values("spearman_deg_btw", ascending=False)
    fig = px.bar(
        df,
        x="region",
        y="spearman_deg_btw",
        color="n_anomalous",
        title="Degree-betweenness correlation by region",
        labels={"spearman_deg_btw": "rho(degree, betweenness)", "n_anomalous": "# anomalous"},
        template="plotly_white",
    )
    fig.add_annotation(
        text="Higher rho = US-like (degree & betweenness agree); "
        "lower = worldwide-like (anomalous gateways).",
        xref="paper", yref="paper", x=0, y=1.08, showarrow=False, font=dict(size=11),
    )
    return fig


def region_spectrum_html(structure: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    ensure_parent(path)
    region_spectrum_figure(structure).write_html(str(path), include_plotlyjs=plotlyjs_ref(path))
    return path


# --------------------------------------------------------------------------- #
# The paper's headline results that the dashboard was missing: dose-response,
# deaths averted (lethal type), and the geographic equity of protection. Each
# reuses the same on-disk aggregation the article figures use, so the app and the
# paper read from one source. Flagship = Europe's full multilayer substrate.
# --------------------------------------------------------------------------- #
_REGION = "europe"
_FLAGSHIP = "air+land+water"


def dose_response_figure(summary: pd.DataFrame) -> go.Figure | None:
    """Peak reduction vs. number of cities vaccinated, per disease, under the
    winning betweenness rule on the flagship (the paper's dose-response). Reads
    the budget sweep already in summary.parquet — no simulation."""
    s = summary[(summary["region"] == _REGION) & (summary["combo"] == _FLAGSHIP)]
    if s.empty:
        return None
    hi = s[s["strategy"] != "control"]["coverage"].max()
    rows = []
    for model in sorted(s["model"].unique()):
        sm = s[s["model"] == model]
        ctrl = sm[sm["strategy"] == "control"].groupby("seed")["peak_infected"].mean()
        ctrl = ctrl[ctrl > 0]
        cand = sm[(sm["strategy"] != "control") & (sm["coverage"] == hi)]
        if cand.empty or ctrl.empty:
            continue
        swept = cand.groupby("strategy")["budget"].nunique()
        swept = swept[swept > 1]
        if swept.empty:
            continue
        winner = "betweenness" if "betweenness" in swept.index else swept.idxmax()
        wcand = cand[cand["strategy"] == winner]
        for b in sorted(wcand["budget"].unique()):
            peak = wcand[wcand["budget"] == b].groupby("seed")["peak_infected"].mean()
            paired = pd.concat([peak.rename("peak"), ctrl.rename("ctrl")],
                               axis=1, join="inner").dropna()
            if paired.empty:
                continue
            red = ((paired["ctrl"] - paired["peak"]) / paired["ctrl"] * 100.0)
            rows.append({"model": model.upper(), "budget": int(b),
                         "reduction": float(red.mean())})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    fig = px.line(
        df, x="budget", y="reduction", color="model", markers=True,
        title="Dose–response: peak reduction vs. cities vaccinated (betweenness, flagship)",
        labels={"budget": "cities vaccinated (budget)",
                "reduction": "peak reduction vs. no vaccination (%)", "model": "disease"},
        template="plotly_white",
    )
    fig.update_yaxes(rangemode="tozero")
    return fig


def deaths_averted_figure(deaths: pd.DataFrame,
                          summary: pd.DataFrame | None = None) -> go.Figure | None:
    """Deaths averted per 100k for the lethal SEIQRD type, per strategy, at the
    operating budget on the flagship. Takes the on-disk ``deaths.parquet`` table
    (``aggregate.deaths_table``) — the metric that makes the lethal type meaningful."""
    if deaths is None or deaths.empty:
        return None
    df = deaths[(deaths["region"] == _REGION) & (deaths["combo"] == _FLAGSHIP)]
    if df.empty:
        return None
    df = df[df["budget"] == df["budget"].min()]
    pop = float("nan")
    if summary is not None and not summary.empty:
        ps = summary[(summary["region"] == _REGION) & (summary["combo"] == _FLAGSHIP)]
        if not ps.empty:
            pop = float(ps["total_population"].iloc[0])
    if not (pop == pop and pop > 0):
        return None
    agg = (df.groupby("strategy", as_index=False)["deaths_averted"].mean())
    agg["per100k"] = agg["deaths_averted"] / pop * 1e5
    agg = agg.sort_values("per100k", ascending=False)
    fig = px.bar(
        agg, x="strategy", y="per100k",
        title="Deaths averted per 100k, lethal type (SEIQRD), flagship",
        labels={"per100k": "deaths averted per 100k (vs no vaccination)", "strategy": "strategy"},
        template="plotly_white",
    )
    return fig


def equity_figure(equity: pd.DataFrame) -> go.Figure | None:
    """Geographic spread of each strategy's chosen cities on the flagship: how many
    countries they touch and how concentrated (Gini). Takes the on-disk
    ``equity.parquet`` table (``aggregate.equity_table``) — pure structure."""
    if equity is None or equity.empty:
        return None
    df = equity
    if "combo" in df.columns:
        df = df[(df["region"] == _REGION) & (df["combo"] == _FLAGSHIP)]
    if df.empty:
        return None
    df = df.sort_values("gini")
    fig = px.bar(
        df, x="strategy", y="gini", color="n_countries",
        title="Protection equity: geographic concentration of the vaccinated set (flagship)",
        labels={"gini": "Gini of per-country counts (0 = even)", "strategy": "strategy",
                "n_countries": "# countries"},
        template="plotly_white",
    )
    fig.add_annotation(
        text="Lower Gini / more countries = protection spread across the continent, not one.",
        xref="paper", yref="paper", x=0, y=1.08, showarrow=False, font=dict(size=11),
    )
    return fig

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

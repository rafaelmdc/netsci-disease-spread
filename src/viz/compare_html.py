"""Cross-experiment comparison plots from the collected summary table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px

from src.paths import ensure_parent


def strategy_comparison_html(summary: pd.DataFrame, path: str | Path) -> Path:
    """Grouped bars: mean peak infections per model, per strategy.

    Averaged over seeds; non-control strategies shown at high coverage so the
    comparison is like-for-like. Lower bars = better containment.
    """
    path = Path(path)
    ensure_parent(path)

    hi = summary["coverage"].max()
    df = summary[(summary["strategy"] == "control") | (summary["coverage"] == hi)]
    agg = (
        df.groupby(["model", "strategy"], as_index=False)["peak_infected"]
        .mean()
        .sort_values("model")
    )
    fig = px.bar(
        agg,
        x="model",
        y="peak_infected",
        color="strategy",
        barmode="group",
        title="Peak active infections by model and vaccination strategy",
        labels={"peak_infected": "mean peak infected (over seeds)", "model": "model"},
        template="plotly_white",
    )
    fig.add_annotation(
        text="Lower is better; targeted strategies should sit below control/random.",
        xref="paper", yref="paper", x=0, y=1.08, showarrow=False, font=dict(size=11),
    )
    fig.write_html(str(path), include_plotlyjs="inline")
    return path

"""Epidemic compartment curves as standalone interactive HTML (plotly)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from src.paths import ensure_parent


def curves_to_html(
    timeseries: pd.DataFrame, path: str | Path, title: str = "Epidemic curves"
) -> Path:
    path = Path(path)
    ensure_parent(path)
    fig = go.Figure()
    for col in timeseries.columns:
        fig.add_trace(go.Scatter(y=timeseries[col], mode="lines", name=col))
    fig.update_layout(
        title=title,
        xaxis_title="day",
        yaxis_title="individuals",
        template="plotly_white",
    )
    fig.write_html(str(path), include_plotlyjs="inline")
    return path

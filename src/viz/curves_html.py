"""Epidemic compartment curves as standalone interactive HTML (plotly).

Two stacked panels:
  * top    — every compartment summed across the region (context; S usually
             dominates the scale);
  * bottom — active infections only (E/I/Q), on their own scale, so the
             epidemic curve is actually visible.

A description block explains the compartments and the experiment, so the
figure is self-explanatory when opened on its own.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.paths import ensure_parent
from src.viz.assets import plotlyjs_ref

_GLOSSARY = {
    "S": "Susceptible (can catch it)",
    "E": "Exposed (infected, not yet infectious)",
    "I": "Infectious (currently spreading)",
    "Q": "Quarantined (isolated)",
    "R": "Recovered / immune",
    "V": "Vaccinated (immunised before the outbreak)",
}
_ACTIVE = ("E", "I", "Q")


def curves_figure(
    timeseries: pd.DataFrame,
    title: str = "Epidemic curves",
    subtitle: str = "",
) -> go.Figure:
    """Build the two-panel compartment figure (shared by HTML export + Dash)."""
    cols = list(timeseries.columns)
    active = [c for c in _ACTIVE if c in cols]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(
            "All compartments — people summed across the region",
            "Active infections (own scale)",
        ),
    )
    for col in cols:
        name = f"{col} — {_GLOSSARY.get(col, col)}"
        fig.add_trace(go.Scatter(y=timeseries[col], mode="lines", name=name), row=1, col=1)
    for col in active:
        fig.add_trace(
            go.Scatter(y=timeseries[col], mode="lines", name=f"{col} (active)", showlegend=False),
            row=2,
            col=1,
        )

    glossary = "  ·  ".join(f"<b>{k}</b>={v}" for k, v in _GLOSSARY.items() if k in cols)
    description = (
        f"{subtitle}<br>"
        "Each line is the number of people in that compartment, summed over every node in the "
        "network, on each simulated day. "
        f"<br>{glossary}"
    )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b><br><sub>{description}</sub>", x=0.02, xanchor="left"),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.18),
        margin=dict(t=130, b=80),
        height=820,
    )
    fig.update_xaxes(title_text="day", row=2, col=1)
    fig.update_yaxes(title_text="people", row=1, col=1)
    fig.update_yaxes(title_text="people", row=2, col=1)
    return fig


def curves_to_html(
    timeseries: pd.DataFrame,
    path: str | Path,
    title: str = "Epidemic curves",
    subtitle: str = "",
) -> Path:
    """Write the compartment figure as a standalone HTML file."""
    path = Path(path)
    ensure_parent(path)
    fig = curves_figure(timeseries, title=title, subtitle=subtitle)
    fig.write_html(str(path), include_plotlyjs=plotlyjs_ref(path))
    return path

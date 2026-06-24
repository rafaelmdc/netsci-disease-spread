"""Animated geographic outbreak as standalone interactive HTML (plotly).

Each node is drawn at its real (lon, lat); marker colour and area grow with the
number of active infections on that day. A play button and a day slider scrub
the outbreak through time. The figure is self-contained (no server, no map
tiles — plotly's built-in geo projection ships the coastlines), so it opens
offline and embeds in the report.

Input is the tidy per-node table written by runner._save_node_timeseries:
columns [day, node, name, lat, lon, infectious].
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.paths import ensure_parent
from src.viz.assets import plotlyjs_ref

_COLORSCALE = "YlOrRd"
_MIN_SIZE, _MAX_SIZE = 4.0, 34.0


def _marker_sizes(inf: np.ndarray, gmax: float) -> np.ndarray:
    # area (not radius) ~ infections, so big outbreaks don't blow up the map
    frac = np.sqrt(np.clip(inf, 0.0, None) / gmax) if gmax > 0 else np.zeros_like(inf)
    return _MIN_SIZE + (_MAX_SIZE - _MIN_SIZE) * frac


def _frame_trace(day_df: pd.DataFrame, gmax: float) -> go.Scattergeo:
    inf = day_df["infectious"].to_numpy()
    return go.Scattergeo(
        lon=day_df["lon"],
        lat=day_df["lat"],
        text=[f"{n}<br>{v:,.0f} infectious" for n, v in zip(day_df["name"], inf, strict=True)],
        hoverinfo="text",
        marker=dict(
            size=_marker_sizes(inf, gmax),
            color=inf,
            cmin=0.0,
            cmax=gmax,
            colorscale=_COLORSCALE,
            line=dict(width=0.3, color="rgba(60,60,60,0.5)"),
            colorbar=dict(title="active<br>infections"),
        ),
    )


def spread_figure(
    node_ts: pd.DataFrame,
    title: str = "Outbreak spread",
    subtitle: str = "",
) -> go.Figure:
    """Build the animated outbreak map (shared by HTML export + Dash)."""
    days = sorted(node_ts["day"].unique())
    by_day = {d: node_ts[node_ts["day"] == d] for d in days}
    gmax = float(node_ts["infectious"].max()) or 1.0

    frames = [
        go.Frame(data=[_frame_trace(by_day[d], gmax)], name=str(d)) for d in days
    ]
    fig = go.Figure(data=[_frame_trace(by_day[days[0]], gmax)], frames=frames)

    steps = [
        dict(method="animate", label=str(d),
             args=[[str(d)], dict(mode="immediate",
                                  frame=dict(duration=0, redraw=True),
                                  transition=dict(duration=0))])
        for d in days
    ]
    fig.update_layout(
        title=dict(text=f"<b>{title}</b><br><sub>{subtitle}</sub>", x=0.02, xanchor="left"),
        margin=dict(t=90, b=10, l=10, r=10),
        height=760,
        geo=dict(fitbounds="locations", showcountries=True, showland=True,
                 landcolor="#f3f3f1", countrycolor="#dddddd", lakecolor="#eaf3f8",
                 showlakes=True, resolution=50),
        updatemenus=[dict(
            type="buttons", x=0.02, y=-0.04, xanchor="left", direction="left",
            buttons=[
                dict(label="▶ play", method="animate",
                     args=[None, dict(fromcurrent=True,
                                      frame=dict(duration=120, redraw=True),
                                      transition=dict(duration=0))]),
                dict(label="❚❚ pause", method="animate",
                     args=[[None], dict(mode="immediate",
                                        frame=dict(duration=0, redraw=False))]),
            ],
        )],
        sliders=[dict(active=0, x=0.12, len=0.84, currentvalue=dict(prefix="day "),
                      steps=steps)],
    )
    return fig


def spread_to_html(
    node_ts: pd.DataFrame,
    path: str | Path,
    title: str = "Outbreak spread",
    subtitle: str = "",
) -> Path:
    """Write the animated outbreak map as a standalone HTML file."""
    path = Path(path)
    ensure_parent(path)
    fig = spread_figure(node_ts, title=title, subtitle=subtitle)
    fig.write_html(str(path), include_plotlyjs=plotlyjs_ref(path), auto_play=False)
    return path

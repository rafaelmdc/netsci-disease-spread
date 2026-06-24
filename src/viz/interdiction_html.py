"""Air-interdiction figure: active-infection curves under scenarios A–D.

The headline is B vs C: in an air-only model (C) grounding flights flattens the
outbreak, but in the real multilayer (B) land and ferry travel keep it going.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from src.paths import ensure_parent
from src.viz.assets import plotlyjs_ref

# A/B/C solid (the headline contrast); D dashed (which closures matter)
_STYLE = {
    "A": dict(color="#444444", dash="solid"),
    "B": dict(color="#d62728", dash="solid"),
    "C": dict(color="#2ca02c", dash="solid"),
    "D1": dict(color="#1f77b4", dash="dash"),
    "D2": dict(color="#9467bd", dash="dash"),
}


def interdiction_figure(results: dict[str, dict], title: str = "Air interdiction") -> go.Figure:
    fig = go.Figure()
    for name, r in results.items():
        tag = name.split(" ")[0]
        peak = r["summary"].get("peak_infected", 0.0)
        fig.add_trace(go.Scatter(
            y=r["infectious"], mode="lines", name=f"{name}  (peak {peak:,.0f})",
            line=dict(width=2.5, **_STYLE.get(tag, {})),
        ))
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><sub>Active infections over time. B vs C is the point: "
            "with land+water open (B) grounding flights does NOT stop the outbreak the way an "
            "air-only model (C) predicts.</sub>",
            x=0.02, xanchor="left",
        ),
        xaxis_title="day", yaxis_title="active infections",
        template="plotly_white", height=720, legend=dict(orientation="h", y=-0.18),
    )
    return fig


def interdiction_to_html(results: dict[str, dict], path: str | Path, title: str = "") -> Path:
    path = Path(path)
    ensure_parent(path)
    interdiction_figure(results, title=title or "Air interdiction").write_html(
        str(path), include_plotlyjs=plotlyjs_ref(path)
    )
    return path

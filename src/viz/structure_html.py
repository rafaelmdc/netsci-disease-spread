"""Per-network structural figure: degree vs betweenness, anomalous gateways.

This is the picture behind the central question. Each node is one city; x is its
degree (how busy), y is its betweenness (how much of a bridge). If the cloud
hugs the diagonal, busy == bridge (US-like, degree-targeting suffices). Points
in the top-left — low degree, high betweenness — are the *anomalous gateways*
(Anchorage-style) where betweenness-targeting would catch a critical city that
degree-targeting misses.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import plotly.graph_objects as go

from src.evaluate.centrality import betweenness
from src.evaluate.metrics import degree_betweenness
from src.paths import ensure_parent
from src.viz.assets import plotlyjs_ref


def structure_figure(graph: nx.DiGraph, title: str = "Degree vs betweenness") -> go.Figure:
    nodes = list(graph.nodes())
    deg = np.array([graph.degree(n) for n in nodes], dtype=float)
    bc_map = betweenness(graph)
    bc = np.array([bc_map[n] for n in nodes], dtype=float)
    db = degree_betweenness(graph)
    rho = db["spearman_deg_btw"]
    anomalous = set(db["anomalous_gateways"])
    names = [str(graph.nodes[n].get("name", n)) for n in nodes]

    is_anom = np.array([n in anomalous for n in nodes])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=deg[~is_anom], y=bc[~is_anom], mode="markers",
        marker=dict(size=6, color="#1f77b4", opacity=0.55), name="typical",
        text=[names[i] for i in range(len(nodes)) if not is_anom[i]], hoverinfo="text+x+y",
    ))
    fig.add_trace(go.Scatter(
        x=deg[is_anom], y=bc[is_anom], mode="markers",
        marker=dict(size=11, color="#d62728", line=dict(width=1, color="#7a0000")),
        name="anomalous gateway (low degree, high betweenness)",
        text=[names[i] for i in range(len(nodes)) if is_anom[i]], hoverinfo="text+x+y",
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><sub>Spearman ρ(degree, betweenness) = {rho:.3f} · "
            f"{int(is_anom.sum())} anomalous gateways · higher ρ ⇒ degree- and "
            "betweenness-targeting coincide (US-like)</sub>",
            x=0.02, xanchor="left",
        ),
        xaxis_title="degree (number of routes — 'how busy')",
        yaxis_title="betweenness ('how much of a bridge')",
        template="plotly_white", height=720, legend=dict(orientation="h", y=-0.15),
    )
    return fig


def structure_to_html(graph: nx.DiGraph, path: str | Path, title: str = "Structure") -> Path:
    path = Path(path)
    ensure_parent(path)
    structure_figure(graph, title=title).write_html(str(path), include_plotlyjs=plotlyjs_ref(path))
    return path

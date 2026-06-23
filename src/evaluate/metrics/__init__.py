"""Network characterization and the degree-betweenness measurement.

The degree-betweenness rank correlation is the decisive structural number
for the novelty: high correlation => US-like regime (degree- and
betweenness-targeted immunization coincide); low correlation or salient
anomalous gateways => worldwide-like regime (they diverge).
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.stats import spearmanr


def characterize(graph: nx.DiGraph) -> dict[str, float]:
    degrees = np.array([d for _, d in graph.degree()], dtype=float)
    k = degrees.mean() if degrees.size else 0.0
    k2 = (degrees**2).mean() if degrees.size else 0.0
    return {
        "n_nodes": float(graph.number_of_nodes()),
        "n_edges": float(graph.number_of_edges()),
        "mean_degree": float(k),
        "k2_over_k": float(k2 / k) if k > 0 else 0.0,
    }


def degree_betweenness(graph: nx.DiGraph, anomaly_quantile: float = 0.75) -> dict:
    """Spearman rho(degree, betweenness) and anomalous gateways
    (low degree, high betweenness)."""
    nodes = list(graph.nodes())
    if len(nodes) < 3:
        return {"spearman_deg_btw": float("nan"), "anomalous_gateways": []}

    deg = np.array([graph.degree(n) for n in nodes], dtype=float)
    bc_map = nx.betweenness_centrality(graph, weight="weight")
    bc = np.array([bc_map[n] for n in nodes], dtype=float)

    rho = float(spearmanr(deg, bc).statistic)

    # anomalous gateway: betweenness above its high quantile but degree below median
    deg_med = np.median(deg)
    bc_hi = np.quantile(bc, anomaly_quantile)
    anomalous = [
        nodes[i] for i in range(len(nodes)) if bc[i] >= bc_hi and deg[i] <= deg_med
    ]
    return {"spearman_deg_btw": rho, "anomalous_gateways": anomalous}

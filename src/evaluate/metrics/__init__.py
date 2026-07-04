"""Network characterization and the degree-betweenness measurement.

The degree-betweenness rank correlation is the decisive structural number
for the novelty: high correlation => US-like regime (degree- and
betweenness-targeted immunization coincide); low correlation or salient
anomalous gateways => worldwide-like regime (they diverge).
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.stats import norm, spearmanr

from src.evaluate.centrality import betweenness


def characterize(graph: nx.DiGraph) -> dict[str, float]:
    degrees = np.array([d for _, d in graph.degree()], dtype=float)
    k = degrees.mean() if degrees.size else 0.0
    k2 = (degrees**2).mean() if degrees.size else 0.0
    apl, diam = _path_metrics(graph)
    return {
        "n_nodes": float(graph.number_of_nodes()),
        "n_edges": float(graph.number_of_edges()),
        "density": float(nx.density(graph)),
        "mean_degree": float(k),
        "k2_over_k": float(k2 / k) if k > 0 else 0.0,
        "assortativity": _assortativity(graph),
        "clustering": _clustering(graph),
        "avg_path_length": apl,
        "diameter": diam,
        "modularity": _modularity(graph),
        "giant_frac": _giant_fraction(graph),
    }


def _undirected_lcc(graph: nx.DiGraph) -> nx.Graph:
    """Largest connected component of the undirected projection — the substrate
    for the path/clustering/community metrics (a directed transport graph is
    effectively undirected for reachability, and these measures need a single
    connected component)."""
    ug = graph.to_undirected()
    if ug.number_of_nodes() == 0:
        return ug
    lcc = max(nx.connected_components(ug), key=len)
    return ug.subgraph(lcc).copy()


def _clustering(graph: nx.DiGraph) -> float:
    """Average (undirected) clustering coefficient — local cohesion / triangles."""
    try:
        return float(nx.average_clustering(graph.to_undirected()))
    except (ZeroDivisionError, nx.NetworkXError):
        return float("nan")


def _path_metrics(graph: nx.DiGraph) -> tuple[float, float]:
    """Average shortest-path length and diameter on the undirected largest
    connected component (small-world signature: short paths -> fast invasion)."""
    lcc = _undirected_lcc(graph)
    if lcc.number_of_nodes() < 2:
        return float("nan"), float("nan")
    try:
        apl = float(nx.average_shortest_path_length(lcc))
        diam = float(nx.diameter(lcc))
    except (nx.NetworkXError, ValueError):
        return float("nan"), float("nan")
    return apl, diam


def _modularity(graph: nx.DiGraph) -> float:
    """Modularity of a Louvain community partition of the undirected projection
    (geographic/community structure; high Q -> outbreaks can be trapped in
    modules, relevant to interdiction and targeted vaccination)."""
    ug = graph.to_undirected()
    if ug.number_of_edges() == 0:
        return float("nan")
    try:
        communities = nx.community.louvain_communities(ug, seed=0)
        return float(nx.community.modularity(ug, communities))
    except (nx.NetworkXError, ZeroDivisionError, ValueError):
        return float("nan")


def _assortativity(graph: nx.DiGraph) -> float:
    """Degree assortativity coefficient; NaN when undefined (e.g. regular graph)."""
    try:
        return float(nx.degree_assortativity_coefficient(graph))
    except (ValueError, ZeroDivisionError, nx.NetworkXError):
        return float("nan")


def _giant_fraction(graph: nx.DiGraph) -> float:
    """Fraction of nodes in the largest (weakly) connected component."""
    n = graph.number_of_nodes()
    if n == 0:
        return 0.0
    components = (
        nx.weakly_connected_components(graph)
        if graph.is_directed()
        else nx.connected_components(graph)
    )
    return max((len(c) for c in components), default=0) / n


def _benjamini_hochberg(pvals: np.ndarray, q: float) -> np.ndarray:
    """Boolean mask of hypotheses rejected under Benjamini-Hochberg FDR at q."""
    n = len(pvals)
    order = np.argsort(pvals)
    thresh = q * (np.arange(1, n + 1) / n)
    passed = pvals[order] <= thresh
    rejected = np.zeros(n, dtype=bool)
    hits = np.where(passed)[0]
    if hits.size:  # reject all up to the largest index that passes (BH step-up)
        rejected[order[: hits.max() + 1]] = True
    return rejected


def anomalous_gateways(
    graph: nx.DiGraph, fdr_q: float = 0.05, n_bins: int = 10
) -> list[str]:
    """Low-degree, high-betweenness 'gateway' airports (Anchorage-style).

    Rather than an arbitrary quantile cut, betweenness is compared *against
    nodes of similar degree*: we bin nodes by degree, standardise betweenness
    within each bin, and flag nodes whose betweenness is significantly above its
    degree peers' under a one-sided test with Benjamini-Hochberg FDR control.
    This is the degree-conditioned anomaly notion benchmarked by Sun, Hu & Zhu
    (2023) for the US network — a node is anomalous only if it bridges far more
    than its number of connections would predict. Restricted to below-median
    degree so we report genuine low-degree gateways, not expected big hubs.
    """
    nodes = list(graph.nodes())
    n = len(nodes)
    if n < 10:
        return []
    deg = np.array([graph.degree(v) for v in nodes], dtype=float)
    bc_map = betweenness(graph)
    bc = np.array([bc_map[v] for v in nodes], dtype=float)

    # z-score of betweenness within each degree bin (peers of similar degree).
    # Bin count adapts to n so every bin keeps enough peers (>= ~8) to estimate
    # a within-degree mean/spread — otherwise a uniquely low-degree gateway has
    # no comparison group and can never be evaluated.
    z = np.full(n, -np.inf)
    order = np.argsort(deg)
    bins = max(1, min(n_bins, n // 8))
    for grp in np.array_split(order, bins):
        if grp.size < 3:
            continue
        mu, sd = bc[grp].mean(), bc[grp].std(ddof=1)
        if sd > 0:
            z[grp] = (bc[grp] - mu) / sd
    pvals = norm.sf(z)  # one-sided upper tail; z = -inf -> p = 1
    rejected = _benjamini_hochberg(pvals, fdr_q)

    deg_med = np.median(deg)
    return [nodes[i] for i in range(n) if rejected[i] and deg[i] <= deg_med]


def degree_betweenness(graph: nx.DiGraph, fdr_q: float = 0.05) -> dict:
    """Spearman rho(degree, betweenness) and the degree-conditioned anomalous
    gateways (see ``anomalous_gateways``)."""
    nodes = list(graph.nodes())
    if len(nodes) < 3:
        return {"spearman_deg_btw": float("nan"), "anomalous_gateways": []}

    deg = np.array([graph.degree(n) for n in nodes], dtype=float)
    bc_map = betweenness(graph)  # cached, topological (see centrality.py)
    bc = np.array([bc_map[n] for n in nodes], dtype=float)
    rho = float(spearmanr(deg, bc).statistic)
    return {"spearman_deg_btw": rho, "anomalous_gateways": anomalous_gateways(graph, fdr_q=fdr_q)}

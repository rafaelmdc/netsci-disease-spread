"""Centrality computations, cached per graph object.

Betweenness is the expensive step and is identical across every run on a
given network (it depends only on topology). A sweep runs the same graph
dozens of times, so we memoise it per graph object — computed once per
process, reused by both the betweenness strategy and the structural metric.

The same per-graph memoisation is used for the two modern targeting scores
added for the vaccination study: Collective Influence (Morone & Makse 2015)
and non-backtracking centrality (largest-eigenvalue impact; Torres et al.).
Both depend only on topology, so each is computed once per process per graph.
"""

from __future__ import annotations

from weakref import WeakKeyDictionary

import networkx as nx
import numpy as np

_betweenness_cache: WeakKeyDictionary[nx.Graph, dict[str, float]] = WeakKeyDictionary()
_ci_cache: WeakKeyDictionary[nx.Graph, dict[int, dict[str, float]]] = WeakKeyDictionary()
_nb_cache: WeakKeyDictionary[nx.Graph, dict[str, object]] = WeakKeyDictionary()


def betweenness(graph: nx.DiGraph) -> dict[str, float]:
    """Unweighted (topological) betweenness centrality, cached per graph.

    Edge ``weight`` is flight frequency, not a distance, so it is deliberately
    NOT passed to ``betweenness_centrality``.
    """
    cached = _betweenness_cache.get(graph)
    if cached is None:
        cached = nx.betweenness_centrality(graph)
        _betweenness_cache[graph] = cached
    return cached


def _undirected(graph: nx.DiGraph) -> nx.Graph:
    return graph.to_undirected() if graph.is_directed() else graph


def collective_influence(graph: nx.DiGraph, radius: int = 2) -> dict[str, float]:
    """Collective Influence score per node (Morone & Makse 2015), cached per
    (graph, radius).

    ``CI_r(i) = (k_i - 1) * sum over j on the frontier Ball(i, r) of (k_j - 1)``,
    where the frontier is the set of nodes at *exactly* distance ``r`` from ``i``.
    This is the non-adaptive (single-pass) CI: we rank once and take the top
    budget, rather than the adaptive remove-and-recompute variant, which would
    re-solve CI after every removal and is far too costly inside a sweep. The
    non-adaptive ranking is the standard cheap approximation and, unlike degree,
    rewards low-degree nodes that sit between high-degree neighbourhoods — the
    anomalous gateways this project already flags. Computed on the undirected
    projection, since reachability here is symmetric.
    """
    per_radius = _ci_cache.setdefault(graph, {})
    cached = per_radius.get(radius)
    if cached is not None:
        return cached
    g = _undirected(graph)
    deg = dict(g.degree())
    ci: dict[str, float] = {}
    for v in g.nodes():
        dist = nx.single_source_shortest_path_length(g, v, cutoff=radius)
        frontier = (u for u, d in dist.items() if d == radius)
        ci[v] = (deg[v] - 1) * float(sum(deg[u] - 1 for u in frontier))
    per_radius[radius] = ci
    return ci


def _hashimoto(g: nx.Graph):
    """Non-backtracking (Hashimoto) operator of an undirected graph, as a sparse
    matrix on its directed edges. ``(B x)_{a->b} = sum over c ~ b, c != a of
    x_{b->c}`` — a walk may not immediately reverse. Returns ``(B, edges)`` where
    ``edges[i]`` is the directed edge for row/col ``i``."""
    from scipy.sparse import csr_matrix

    edges: list[tuple[str, str]] = []
    for u, v in g.edges():
        edges.append((u, v))
        edges.append((v, u))
    index = {e: i for i, e in enumerate(edges)}
    rows, cols = [], []
    for (a, b), i in index.items():
        for c in g.neighbors(b):
            if c != a:
                rows.append(i)
                cols.append(index[(b, c)])
    m = len(edges)
    data = np.ones(len(rows), dtype=float)
    return csr_matrix((data, (rows, cols)), shape=(m, m)), edges


def _nb_solve(graph: nx.DiGraph) -> dict[str, object]:
    """Leading eigenvalue/eigenvector of the non-backtracking matrix, mapped to a
    per-node importance. Cached per graph. ``scores[i]`` sums the leading
    eigenvector mass on the directed edges pointing *into* node ``i`` — the
    node-level non-backtracking centrality used for immunisation."""
    from scipy.sparse.linalg import eigs

    cached = _nb_cache.get(graph)
    if cached is not None:
        return cached
    g = _undirected(graph)
    result: dict[str, object]
    if g.number_of_edges() == 0:
        result = {"eigenvalue": 0.0, "scores": {n: 0.0 for n in g.nodes()}}
        _nb_cache[graph] = result
        return result
    B, edges = _hashimoto(g)
    try:
        vals, vecs = eigs(B.astype(float), k=1, which="LM", maxiter=5000)
        lam = float(abs(vals[0]))
        vec = np.abs(vecs[:, 0].real)
    except Exception:  # eigs may fail to converge on small/degenerate graphs
        lam = float("nan")
        vec = np.ones(len(edges))
    scores: dict[str, float] = dict.fromkeys(g.nodes(), 0.0)
    for (_a, b), val in zip(edges, vec, strict=True):
        scores[b] += float(val)  # mass on edges arriving at b
    result = {"eigenvalue": lam, "scores": scores}
    _nb_cache[graph] = result
    return result


def nonbacktracking_scores(graph: nx.DiGraph) -> dict[str, float]:
    """Per-node non-backtracking centrality (see :func:`_nb_solve`)."""
    return _nb_solve(graph)["scores"]  # type: ignore[return-value]


def nb_leading_eigenvalue(graph: nx.DiGraph) -> float:
    """Largest eigenvalue of the non-backtracking matrix. Its reciprocal is the
    analytic SIR / bond-percolation epidemic threshold (Karrer & Newman; Torres
    et al.): a disease with transmissibility above ``1 / lambda_max`` invades.
    Used for the threshold-position verification (see RESEARCH-ROADMAP #3)."""
    return float(_nb_solve(graph)["eigenvalue"])  # type: ignore[arg-type]

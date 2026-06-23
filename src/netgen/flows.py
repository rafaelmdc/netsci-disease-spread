"""Mobility-flow generation — the radiation model (Simini et al. 2012).

Used to estimate land (commuting/ground) flow weights from population and
geography, the *same way for every region* so cross-region comparison stays
valid (see docs/METHODOLOGY.md). Eurostat is used only to validate this model
within Europe, never as the production source for one region while others use
the model.

The radiation flux from i to j is
    T_ij = T_i * (m_i n_j) / ((m_i + s_ij)(m_i + n_j + s_ij))
where m_i, n_j are populations and s_ij is the total population in the circle
of radius dist(i, j) centred on i (excluding i and j).
"""

from __future__ import annotations

import numpy as np


def haversine_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distance matrix (km) for arrays of lat/lon."""
    rlat = np.radians(lat)
    rlon = np.radians(lon)
    dlat = rlat[:, None] - rlat[None, :]
    dlon = rlon[:, None] - rlon[None, :]
    coslat = np.cos(rlat)
    a = np.sin(dlat / 2) ** 2 + coslat[:, None] * coslat[None, :] * np.sin(dlon / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def radiation_flows(pop: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Radiation-model flux matrix T_ij (zero diagonal). Outflow T_i is taken
    proportional to population (T_i = m_i)."""
    n = len(pop)
    dist = haversine_km(lat, lon)
    flux = np.zeros((n, n))
    order = np.argsort(dist, axis=1)  # nearest-first per origin
    for i in range(n):
        m_i = pop[i]
        if m_i <= 0:
            continue
        s = 0.0  # population in the growing radius, excluding i and j
        idx = order[i]
        for j in idx:
            if j == i:
                continue
            n_j = pop[j]
            denom = (m_i + s) * (m_i + n_j + s)
            if denom > 0:
                flux[i, j] = m_i * (m_i * n_j) / denom
            s += n_j
    return flux


def top_k_edges(flux: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    """Keep each origin's k largest outgoing flows (sparse, commuting-like)."""
    edges: list[tuple[int, int, float]] = []
    for i in range(flux.shape[0]):
        row = flux[i]
        if not row.any():
            continue
        for j in np.argsort(row)[::-1][:k]:
            if row[j] > 0:
                edges.append((i, int(j), float(row[j])))
    return edges

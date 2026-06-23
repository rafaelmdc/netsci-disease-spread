"""Metapopulation reaction-diffusion engine.

Each node runs a compartmental model (reaction); a fraction of every
compartment migrates along edges each day (diffusion). Immunization
converts a fraction of susceptibles at target nodes into the immune sink
before the simulation starts. The run is a pure function of (config, seed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from src.config import RunConfig
from src.evaluate.models import get_model
from src.evaluate.models.base import VACCINATED, CompartmentalModel, State
from src.evaluate.strategies import select_targets


@dataclass
class SimResult:
    nodes: list[str]
    compartments: list[str]
    timeseries: dict[str, list[float]]  # compartment -> daily total
    targets: list[str]
    seed_node: str
    summary: dict[str, float] = field(default_factory=dict)


def _migration_matrix(graph: nx.DiGraph, nodes: list[str], tau: float) -> np.ndarray:
    """M[i, j] = fraction of i's compartment that moves i->j per day = tau * w_ij.
    Row sums are capped below 1 so a node never exports more than it has."""
    idx = {n: k for k, n in enumerate(nodes)}
    n = len(nodes)
    m = np.zeros((n, n), dtype=float)
    for u, v, data in graph.edges(data=True):
        m[idx[u], idx[v]] += tau * float(data.get("weight", 1.0))
    row = m.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(row > 0.99, 0.99 / row, 1.0)  # keep outflow < 1
    return m * scale


def _diffuse(comp: np.ndarray, m: np.ndarray, row_out: np.ndarray) -> np.ndarray:
    """new_j = comp_j - outflow_j + inflow_j, inflow = M^T @ comp."""
    return comp - comp * row_out + m.T @ comp


def simulate(graph: nx.DiGraph, cfg: RunConfig) -> SimResult:
    nodes = list(graph.nodes())
    rng = np.random.default_rng(cfg.sim.seed)
    model: CompartmentalModel = get_model(cfg.model.name)

    population = np.array([float(graph.nodes[n].get("population", 0.0)) for n in nodes])
    seed_node = int(rng.integers(len(nodes)))

    state: State = model.init_state(population, seed_node, cfg.sim.seed_size)
    # engine-owned, inert vaccinated compartment (correct for every model)
    state[VACCINATED] = np.zeros_like(population, dtype=float)
    tracked = [*model.compartments, VACCINATED]

    # immunization: move coverage*efficacy of S -> V at targets, before t=0
    targets = select_targets(graph, cfg.strategy, rng)
    if targets:
        frac = cfg.strategy.coverage * cfg.strategy.efficacy
        tset = set(targets)
        mask = np.array([n in tset for n in nodes])
        protected = state[model.susceptible_key] * frac * mask
        state[model.susceptible_key] -= protected
        state[VACCINATED] += protected

    m = _migration_matrix(graph, nodes, cfg.sim.tau)
    row_out = m.sum(axis=1)

    ts: dict[str, list[float]] = {c: [] for c in tracked}
    for _ in range(cfg.sim.horizon):
        reacted = model.reaction(state, cfg.model.params)
        reacted[VACCINATED] = state[VACCINATED]  # V is inert under reaction
        for c in tracked:
            state[c] = np.clip(_diffuse(reacted[c], m, row_out), 0.0, None)
            ts[c].append(float(state[c].sum()))

    inf = np.array(ts[model.infectious_key])
    summary = {
        "peak_infected": float(inf.max()),
        "time_to_peak": float(int(inf.argmax())),
        "final_infected": float(inf[-1]),
        "total_population": float(population.sum()),
        "vaccinated": float(ts[VACCINATED][-1]),
    }
    if "R" in model.compartments:
        summary["final_recovered"] = float(ts["R"][-1])

    return SimResult(
        nodes=nodes,
        compartments=tracked,
        timeseries=ts,
        targets=targets,
        seed_node=nodes[seed_node],
        summary=summary,
    )

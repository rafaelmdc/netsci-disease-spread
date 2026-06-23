"""Metapopulation reaction-diffusion engine.

Each node runs a compartmental model (reaction); a fraction of every
compartment migrates along edges (diffusion). Edges may carry per-layer
weights and the engine can apply a distinct travel rate per layer. Each day
is optionally split into ``steps_per_day`` sub-steps so the discrete Euler
update converges to the continuous dynamics (used by the verification tests).
Immunization converts a fraction of susceptibles at target nodes into the
inert vaccinated compartment before t=0. The run is a pure function of
(config, seed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from src.config import ModelParams, RunConfig, SimConfig
from src.evaluate.models import get_model
from src.evaluate.models.base import VACCINATED, CompartmentalModel, State
from src.evaluate.strategies import select_targets

_RATE_FIELDS = ("beta", "gamma", "sigma", "kappa", "gamma_q")


@dataclass
class SimResult:
    nodes: list[str]
    compartments: list[str]
    timeseries: dict[str, list[float]]  # compartment -> daily total
    targets: list[str]
    seed_node: str
    summary: dict[str, float] = field(default_factory=dict)
    node_infectious: list[np.ndarray] | None = None  # per-day per-node I (if recorded)


def _edge_rate(data: dict, sim: SimConfig) -> float:
    """Per-day migration fraction contributed by one edge, summing per-layer
    weights at their per-layer travel rate (falling back to the global tau)."""
    if sim.tau_by_layer is None:
        return sim.tau * float(data.get("weight", 1.0))
    contrib, saw_layer = 0.0, False
    for key, w in data.items():
        if key.startswith("w_") and w:
            contrib += sim.tau_by_layer.get(key[2:], sim.tau) * float(w)
            saw_layer = True
    return contrib if saw_layer else sim.tau * float(data.get("weight", 1.0))


def _migration_matrix(graph: nx.DiGraph, nodes: list[str], sim: SimConfig) -> np.ndarray:
    """M[i, j] = per-day fraction of i's compartment that moves i->j.
    Row sums are capped below 1 so a node never exports more than it has."""
    idx = {n: k for k, n in enumerate(nodes)}
    m = np.zeros((len(nodes), len(nodes)), dtype=float)
    for u, v, data in graph.edges(data=True):
        m[idx[u], idx[v]] += _edge_rate(data, sim)
    row = m.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(row > 0.99, 0.99 / row, 1.0)
    return m * scale


def _diffuse(comp: np.ndarray, m: np.ndarray, row_out: np.ndarray) -> np.ndarray:
    return comp - comp * row_out + m.T @ comp


def _scale_rates(params: ModelParams, factor: float) -> ModelParams:
    update = {
        f: getattr(params, f) * factor for f in _RATE_FIELDS if getattr(params, f) is not None
    }
    return params.model_copy(update=update)


def simulate(graph: nx.DiGraph, cfg: RunConfig, record_nodes: bool = False) -> SimResult:
    nodes = list(graph.nodes())
    rng = np.random.default_rng(cfg.sim.seed)
    model: CompartmentalModel = get_model(cfg.model.name)

    population = np.array([float(graph.nodes[n].get("population", 0.0)) for n in nodes])
    seed_node = int(rng.integers(len(nodes)))

    state: State = model.init_state(population, seed_node, cfg.sim.seed_size)
    state[VACCINATED] = np.zeros_like(population, dtype=float)
    tracked = [*model.compartments, VACCINATED]

    targets = select_targets(graph, cfg.strategy, rng)
    if targets:
        frac = cfg.strategy.coverage * cfg.strategy.efficacy
        mask = np.array([n in set(targets) for n in nodes])
        protected = state[model.susceptible_key] * frac * mask
        state[model.susceptible_key] -= protected
        state[VACCINATED] += protected

    sub = cfg.sim.steps_per_day
    m = _migration_matrix(graph, nodes, cfg.sim) / sub
    row_out = m.sum(axis=1)
    sub_params = _scale_rates(cfg.model.params, 1.0 / sub)

    ts: dict[str, list[float]] = {c: [] for c in tracked}
    node_inf: list[np.ndarray] = []
    for _ in range(cfg.sim.horizon):
        for _ in range(sub):
            reacted = model.reaction(state, sub_params)
            reacted[VACCINATED] = state[VACCINATED]  # inert under reaction
            for c in tracked:
                state[c] = np.clip(_diffuse(reacted[c], m, row_out), 0.0, None)
        for c in tracked:
            ts[c].append(float(state[c].sum()))
        if record_nodes:
            node_inf.append(state[model.infectious_key].copy())

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
        node_infectious=node_inf if record_nodes else None,
    )

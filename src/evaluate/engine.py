"""Metapopulation reaction-diffusion engine with two mobility mechanisms.

Each city runs a compartmental model. Mobility is split by type, as the
literature requires (Balcan & Vespignani 2011; Gomez/Arenas movement-
interaction-return; Keeling & Rohani commuter coupling):

* **Diffusive** layers (air, water): a fraction of every compartment
  relocates along edges each day and mixes at the destination.
* **Recurrent** layer (land/commuting): residents commute to neighbours by
  day, mix there, and return home at night — they are NOT relocated. This is
  implemented as a coupling of the *force of infection*: the pressure on city
  i's residents is ``sum_j C_ij * (I*_j / N*_j)`` where ``I*_j, N*_j`` are the
  infectious and total people *present* at j, and C is the per-capita
  commuting matrix (the land radiation kernel, with a stay-home diagonal).

With no land layer C is the identity and pressure reduces to ``I_i/N_i`` — the
plain diffusive model. The run is a pure function of (config, seed).
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
_DEFAULT_LAND_COMMUTE = 0.3  # commuting participation fraction if land has no explicit rate


@dataclass
class SimResult:
    nodes: list[str]
    compartments: list[str]
    timeseries: dict[str, list[float]]
    targets: list[str]
    seed_node: str
    summary: dict[str, float] = field(default_factory=dict)
    node_infectious: list[np.ndarray] | None = None


# --- mobility operators -----------------------------------------------------

def diffusion_rate(data: dict, sim: SimConfig) -> float:
    """Per-day relocation fraction of an edge from its air+water weights only
    (land is recurrent, handled separately). Generic edges with no per-layer
    keys (toy/air-only) are treated as diffusion at the base tau."""
    if not any(k in data for k in ("w_air", "w_water", "w_land")):
        return sim.tau * float(data.get("weight", 1.0))
    tbl = sim.tau_by_layer
    air_r = tbl.get("air", sim.tau) if tbl else sim.tau
    water_r = tbl.get("water", sim.tau) if tbl else sim.tau
    return air_r * float(data.get("w_air", 0.0)) + water_r * float(data.get("w_water", 0.0))


def _diffusion_matrix(graph: nx.DiGraph, nodes: list[str], sim: SimConfig) -> np.ndarray:
    idx = {n: k for k, n in enumerate(nodes)}
    m = np.zeros((len(nodes), len(nodes)), dtype=float)
    for u, v, data in graph.edges(data=True):
        r = diffusion_rate(data, sim)
        if r:
            m[idx[u], idx[v]] += r
    row = m.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(row > 0.99, 0.99 / row, 1.0)
    return m * scale


def _commuting_matrix(graph: nx.DiGraph, nodes: list[str], sim: SimConfig) -> np.ndarray | None:
    """Row-stochastic commuting matrix C (C_ii = stay-home), from land per-capita
    kernels times the land commuting rate. None if the network has no land layer."""
    idx = {n: k for k, n in enumerate(nodes)}
    tbl = sim.tau_by_layer
    rate = tbl.get("land", _DEFAULT_LAND_COMMUTE) if tbl else _DEFAULT_LAND_COMMUTE
    n = len(nodes)
    c = np.zeros((n, n), dtype=float)
    saw_land = False
    for u, v, data in graph.edges(data=True):
        wl = float(data.get("w_land", 0.0))
        if wl > 0:
            c[idx[u], idx[v]] += rate * wl
            saw_land = True
    if not saw_land:
        return None
    row = c.sum(axis=1)
    over = row > 0.99
    if over.any():
        c[over] *= (0.99 / row[over])[:, None]
        row = c.sum(axis=1)
    c[np.diag_indices(n)] += 1.0 - row  # stay-home fraction
    return c


def _pressure(model: CompartmentalModel, state: State, c: np.ndarray | None) -> np.ndarray:
    inf = model.infectious(state)
    mix = model.mixing_pop(state)
    if c is None:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(mix > 0, inf / mix, 0.0)
    present_pop = c.T @ mix
    present_inf = c.T @ inf
    with np.errstate(divide="ignore", invalid="ignore"):
        local = np.where(present_pop > 0, present_inf / present_pop, 0.0)
    return c @ local


def _diffuse(comp: np.ndarray, m: np.ndarray, row_out: np.ndarray) -> np.ndarray:
    return comp - comp * row_out + m.T @ comp


def _scale_rates(params: ModelParams, factor: float) -> ModelParams:
    update = {
        f: getattr(params, f) * factor for f in _RATE_FIELDS if getattr(params, f) is not None
    }
    return params.model_copy(update=update)


# --- simulation -------------------------------------------------------------

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
    commute = _commuting_matrix(graph, nodes, cfg.sim)
    m = _diffusion_matrix(graph, nodes, cfg.sim) / sub
    row_out = m.sum(axis=1)
    sub_params = _scale_rates(cfg.model.params, 1.0 / sub)

    ts: dict[str, list[float]] = {c: [] for c in tracked}
    node_inf: list[np.ndarray] = []
    for _ in range(cfg.sim.horizon):
        for _ in range(sub):
            pressure = _pressure(model, state, commute)
            reacted = model.reaction(state, sub_params, pressure)
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

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

from collections.abc import Callable
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from src.config import ModelParams, RunConfig, SimConfig
from src.evaluate.models import get_model
from src.evaluate.models.base import VACCINATED, CompartmentalModel, State
from src.evaluate.strategies import select_targets
from src.netgen.flows import haversine_point

#: called after each simulated day with (absolute_day_index, compartment_totals)
ProgressFn = Callable[[int, dict[str, float]], None]
#: called every N days with (absolute_day_index, per-node infectious array)
NodeProgressFn = Callable[[int, "np.ndarray"], None]

_RATE_FIELDS = ("beta", "gamma", "sigma", "kappa", "gamma_q", "omega")  # mu is a fraction, not a rate
_DEFAULT_LAND_COMMUTE = 0.3  # commuting participation fraction if land has no explicit rate

# Default in-transit transmission per layer: trip duration = distance/speed, so
# long confined trips (ferries) dominate; `beta` is the onboard contact rate and
# `control` in [0,1] is onboard-intervention effectiveness.
_TRANSIT_DEFAULTS: dict[str, dict[str, float]] = {
    "air": {"speed_kmh": 800.0, "beta": 0.10, "control": 0.0},
    "water": {"speed_kmh": 40.0, "beta": 0.30, "control": 0.0},
    "land": {"speed_kmh": 60.0, "beta": 0.05, "control": 0.0},
}


def _transit_params(transit: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {layer: {**d, **transit.get(layer, {})} for layer, d in _TRANSIT_DEFAULTS.items()}


@dataclass
class SimResult:
    nodes: list[str]
    compartments: list[str]
    timeseries: dict[str, list[float]]
    targets: list[str]
    seed_node: str
    summary: dict[str, float] = field(default_factory=dict)
    node_infectious: list[np.ndarray] | None = None
    #: per-node compartment arrays at the final day — the resume checkpoint
    final_state: State | None = None


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


def _layer_diffusion(
    graph: nx.DiGraph, nodes: list[str], sim: SimConfig
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Per-diffusive-layer migration matrices {air, water}, jointly row-capped,
    plus their sum (the combined diffusion operator)."""
    idx = {n: k for k, n in enumerate(nodes)}
    n = len(nodes)
    tbl = sim.tau_by_layer
    mats: dict[str, np.ndarray] = {}
    for u, v, data in graph.edges(data=True):
        i, j = idx[u], idx[v]
        if not any(k in data for k in ("w_air", "w_water", "w_land")):
            w = float(data.get("weight", 1.0))
            mats.setdefault("air", np.zeros((n, n)))[i, j] += sim.tau * w
            continue
        for layer in ("air", "water"):
            w = float(data.get(f"w_{layer}", 0.0))
            if w > 0:
                rate = tbl.get(layer, sim.tau) if tbl else sim.tau
                mats.setdefault(layer, np.zeros((n, n)))[i, j] += rate * w
    combined = sum(mats.values()) if mats else np.zeros((n, n))
    row = combined.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(row > 0.99, 0.99 / row, 1.0)
    for layer in mats:
        mats[layer] = mats[layer] * scale
    return mats, combined * scale


def _transit_setup(graph: nx.DiGraph, nodes: list[str], sim: SimConfig) -> dict | None:
    """Per-layer onboard params and mean trip duration (days), or None if off.
    Duration = distance/speed, so long confined trips (ferries) get more
    in-transit dynamics than short ones (flights, commutes)."""
    if sim.transit is None:
        return None
    p = _transit_params(sim.transit)
    idx = {n: k for k, n in enumerate(nodes)}
    lat = np.array([float(graph.nodes[n].get("lat", 0.0)) for n in nodes])
    lon = np.array([float(graph.nodes[n].get("lon", 0.0)) for n in nodes])
    acc = {layer: [0.0, 0] for layer in ("air", "water", "land")}
    for u, v, data in graph.edges(data=True):
        i, j = idx[u], idx[v]
        d_km = float(haversine_point(lat[i], lon[i], lat[j : j + 1], lon[j : j + 1])[0])
        if d_km <= 0:
            continue
        for layer in ("air", "water", "land"):
            if float(data.get(f"w_{layer}", 0.0)) > 0:
                acc[layer][0] += d_km / p[layer]["speed_kmh"] / 24.0
                acc[layer][1] += 1
    dur = {layer: (s / c if c else 0.0) for layer, (s, c) in acc.items()}
    return {"params": p, "dur": dur}


def _transit_model_params(base: ModelParams, beta_transit: float, control: float, dur: float):
    """Model params for one trip: rates x trip-duration, transmission at the
    onboard contact rate reduced by onboard control."""
    eff = (1.0 - control) * dur
    update = {"beta": beta_transit * eff}
    for f in ("gamma", "sigma", "kappa", "gamma_q"):
        v = getattr(base, f, None)
        if v is not None:
            update[f] = v * dur
    return base.model_copy(update=update)


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

def summarize(
    ts: dict[str, list[float]], model: CompartmentalModel, total_population: float
) -> dict[str, float]:
    """Headline stats from a (possibly extended) compartment time series."""
    inf = np.array(ts[model.infectious_key])
    summary = {
        "peak_infected": float(inf.max()),
        "time_to_peak": float(int(inf.argmax())),
        "final_infected": float(inf[-1]),
        "total_population": total_population,
        "vaccinated": float(ts[VACCINATED][-1]),
    }
    if "R" in model.compartments:
        summary["final_recovered"] = float(ts["R"][-1])
    return summary


def simulate(
    graph: nx.DiGraph,
    cfg: RunConfig,
    record_nodes: bool = False,
    progress: ProgressFn | None = None,
    init_state: State | None = None,
    day_offset: int = 0,
    node_progress: NodeProgressFn | None = None,
    node_every: int = 1,
) -> SimResult:
    """Run the metapopulation dynamics for ``cfg.sim.horizon`` days.

    ``progress(day, totals)`` — if given — is called after each simulated day
    with the absolute day index (``day_offset + i``) and that day's compartment
    totals, so a caller can stream the outbreak as it builds.

    ``node_progress(day, infectious)`` — if given — is called every
    ``node_every`` days with the per-node infectious vector, for a live map
    (throttled because the per-node payload is much larger than the totals).

    ``init_state`` — if given — *resumes* from that per-node ``State`` instead of
    starting fresh: initial seeding and vaccination are skipped (they already
    happened in the original run), and only ``cfg.sim.horizon`` *more* days are
    simulated. ``day_offset`` is the number of days already elapsed, used purely
    for the ``progress`` day index. See ``runner.continue_run``.
    """
    nodes = list(graph.nodes())
    rng = np.random.default_rng(cfg.sim.seed)
    model: CompartmentalModel = get_model(cfg.model.name)

    population = np.array([float(graph.nodes[n].get("population", 0.0)) for n in nodes])
    tracked = [*model.compartments, VACCINATED]

    if init_state is None:
        seed_node = int(rng.integers(len(nodes)))
        state: State = model.init_state(population, seed_node, cfg.sim.seed_size)
        state[VACCINATED] = np.zeros_like(population, dtype=float)

        targets = select_targets(graph, cfg.strategy, rng)
        if targets:
            frac = cfg.strategy.coverage * cfg.strategy.efficacy
            mask = np.array([n in set(targets) for n in nodes])
            protected = state[model.susceptible_key] * frac * mask
            state[model.susceptible_key] -= protected
            state[VACCINATED] += protected
    else:
        # resume: start from the saved state; no re-seeding / re-vaccinating.
        state = {c: np.asarray(init_state[c], dtype=float).copy() for c in tracked}
        seed_node = -1
        targets = []

    sub = cfg.sim.steps_per_day
    commute = _commuting_matrix(graph, nodes, cfg.sim)
    layer_m, m_combined = _layer_diffusion(graph, nodes, cfg.sim)
    layer_m = {layer: mat / sub for layer, mat in layer_m.items()}
    m_combined = m_combined / sub
    row_out = m_combined.sum(axis=1)
    sub_params = _scale_rates(cfg.model.params, 1.0 / sub)

    # in-transit: per-layer trip params (full reaction on the cohort during the
    # trip, so travellers can be infected AND recover/incubate/quarantine).
    transit = _transit_setup(graph, nodes, cfg.sim)
    t_params = None
    a_land = None
    if transit is not None:
        t_params = {
            layer: _transit_model_params(
                cfg.model.params, transit["params"][layer]["beta"],
                transit["params"][layer]["control"], transit["dur"][layer],
            )
            for layer in ("air", "water", "land")
        }
        a_land = (1.0 - np.diag(commute)) if commute is not None else None

    ts: dict[str, list[float]] = {c: [] for c in tracked}
    node_inf: list[np.ndarray] = []
    for day in range(cfg.sim.horizon):
        for _ in range(sub):
            pressure = _pressure(model, state, commute)
            reacted = model.reaction(state, sub_params, pressure)
            reacted[VACCINATED] = state[VACCINATED]  # inert under reaction

            if transit is None:
                for c in tracked:
                    state[c] = np.clip(_diffuse(reacted[c], m_combined, row_out), 0.0, None)
            else:
                vehicle_p = _pressure(model, reacted, None)  # confined cohort mixing
                # each diffusive cohort undergoes its trip's dynamics, then arrives
                rt = {}
                for layer in layer_m:
                    r = model.reaction(reacted, t_params[layer], vehicle_p)
                    r[VACCINATED] = reacted[VACCINATED]
                    rt[layer] = r
                land_delta = None
                if a_land is not None:
                    rl = model.reaction(reacted, t_params["land"], vehicle_p)
                    rl[VACCINATED] = reacted[VACCINATED]
                    land_delta = {c: a_land * (rl[c] - reacted[c]) for c in tracked}
                for c in tracked:
                    inflow = sum(layer_m[layer].T @ rt[layer][c] for layer in layer_m)
                    new = reacted[c] - row_out * reacted[c] + inflow
                    if land_delta is not None:
                        new = new + land_delta[c]
                    state[c] = np.clip(new, 0.0, None)
        for c in tracked:
            ts[c].append(float(state[c].sum()))
        if record_nodes:
            node_inf.append(state[model.infectious_key].copy())
        if progress is not None:
            progress(day_offset + day, {c: ts[c][-1] for c in tracked})
        if node_progress is not None and (day % node_every == 0 or day == cfg.sim.horizon - 1):
            node_progress(day_offset + day, state[model.infectious_key])

    summary = summarize(ts, model, float(population.sum()))

    return SimResult(
        nodes=nodes,
        compartments=tracked,
        timeseries=ts,
        targets=targets,
        seed_node=nodes[seed_node] if seed_node >= 0 else "",
        summary=summary,
        node_infectious=node_inf if record_nodes else None,
        final_state={c: state[c].copy() for c in tracked},
    )

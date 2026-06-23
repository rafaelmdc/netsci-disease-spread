"""Interface for compartmental models in the metapopulation engine.

The model advances local disease compartments by one day. The engine supplies
the per-node infection *pressure* (the effective infectious fraction a city's
residents are exposed to), which is computed either locally (``I_i / N_i``) or
with recurrent commuting coupling (residents mix where they commute and return
home) — see engine.py. This separation lets the same models run under both
diffusive and recurrent mobility.

Diffusion (relocation by air/water) and immunization are handled generically by
the engine, via an inert ``V`` (vaccinated) compartment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from src.config import ModelParams

State = dict[str, np.ndarray]

#: engine-owned vaccinated compartment, shared by every model
VACCINATED = "V"


class CompartmentalModel(ABC):
    #: ordered *disease* compartment names, e.g. ["S", "I", "R"] (no "V")
    compartments: list[str]
    susceptible_key: str = "S"
    infectious_key: str = "I"
    #: compartment a newly-infected susceptible enters (E for SEIR, else I)
    entry_key: str = "I"

    def init_state(self, population: np.ndarray, seed_node: int, seed_size: int) -> State:
        """All susceptible except `seed_size` infectious at `seed_node`."""
        state: State = {c: np.zeros_like(population, dtype=float) for c in self.compartments}
        state[self.susceptible_key] = population.astype(float).copy()
        seed = min(float(seed_size), float(population[seed_node]))
        state[self.susceptible_key][seed_node] -= seed
        state[self.infectious_key][seed_node] += seed
        return state

    def infectious(self, state: State) -> np.ndarray:
        """Per-node infectious count that drives transmission."""
        return state[self.infectious_key]

    def mixing_pop(self, state: State) -> np.ndarray:
        """Per-node population that mixes (denominator of the force of infection).
        SQIR overrides this to exclude the isolated Quarantined compartment."""
        return sum(state[c] for c in self.compartments)

    @abstractmethod
    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        """Advance local dynamics one day. ``pressure_i`` is the effective
        infectious fraction; new infections of susceptibles are
        ``beta * pressure * S``."""

"""Interface for compartmental models in the metapopulation engine.

A model is the *reaction* half of the reaction-diffusion process: it
advances per-node disease compartments by one local day. Diffusion
(migration) and immunization are handled generically by the engine.

Immunization uses a universal, inert ``V`` (vaccinated) compartment owned by
the engine — never a disease compartment. This keeps vaccination correct
and uniform across models: a vaccinated individual is removed from ``S`` and
plays no further part in the dynamics, which is true even for SIS (where
there is no recovered/immune compartment at all).
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

    def init_state(self, population: np.ndarray, seed_node: int, seed_size: int) -> State:
        """All susceptible except `seed_size` infectious at `seed_node`."""
        state: State = {c: np.zeros_like(population, dtype=float) for c in self.compartments}
        state[self.susceptible_key] = population.astype(float).copy()
        seed = min(float(seed_size), float(population[seed_node]))
        state[self.susceptible_key][seed_node] -= seed
        state[self.infectious_key][seed_node] += seed
        return state

    @abstractmethod
    def reaction(self, state: State, params: ModelParams) -> State:
        """Advance local dynamics by one day (returns a new state)."""

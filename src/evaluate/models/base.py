"""Interface for compartmental models in the metapopulation engine.

A model is the *reaction* half of the reaction-diffusion process: it
advances per-node compartment counts by one local day. Diffusion
(migration) and immunization are handled generically by the engine, which
only needs to know which compartment is susceptible, infectious, and the
immune sink.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from src.config import ModelParams

State = dict[str, np.ndarray]


class CompartmentalModel(ABC):
    #: ordered compartment names, e.g. ["S", "I", "R"]
    compartments: list[str]
    susceptible_key: str = "S"
    infectious_key: str = "I"
    #: compartment that immunized individuals move into (None if no sink, e.g. SIS)
    immune_key: str | None = "R"

    def init_state(self, population: np.ndarray, seed_node: int, seed_size: int) -> State:
        """All susceptible except `seed_size` infectious at `seed_node`."""
        state: State = {c: np.zeros_like(population, dtype=float) for c in self.compartments}
        state[self.susceptible_key] = population.astype(float).copy()
        seed = min(seed_size, float(population[seed_node]))
        state[self.susceptible_key][seed_node] -= seed
        state[self.infectious_key][seed_node] += seed
        return state

    @abstractmethod
    def reaction(self, state: State, params: ModelParams) -> State:
        """Advance local dynamics by one day (returns a new state)."""

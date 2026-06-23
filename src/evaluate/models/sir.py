"""SIR: Susceptible -> Infectious -> Recovered (permanent immunity)."""

from __future__ import annotations

import numpy as np

from src.config import ModelParams
from src.evaluate.models.base import CompartmentalModel, State


class SIR(CompartmentalModel):
    compartments = ["S", "I", "R"]

    def reaction(self, state: State, params: ModelParams) -> State:
        s, i, r = state["S"], state["I"], state["R"]
        n = s + i + r
        # avoid division by zero in empty subpopulations
        with np.errstate(divide="ignore", invalid="ignore"):
            force = np.where(n > 0, params.beta * i / n, 0.0)
        new_inf = np.minimum(force * s, s)
        new_rec = np.minimum(params.gamma * i, i)
        return {
            "S": s - new_inf,
            "I": i + new_inf - new_rec,
            "R": r + new_rec,
        }

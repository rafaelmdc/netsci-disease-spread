"""SIR: Susceptible -> Infectious -> Recovered (permanent immunity).

e.g. measles, smallpox. Local reproduction number R0_local = beta / gamma.
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SIR)
class SIR(CompartmentalModel):
    compartments = ["S", "I", "R"]

    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        s, i, r = state["S"], state["I"], state["R"]
        new_inf = np.minimum(params.beta * pressure * s, s)
        new_rec = np.minimum(params.gamma * i, i)
        return {"S": s - new_inf, "I": i + new_inf - new_rec, "R": r + new_rec}

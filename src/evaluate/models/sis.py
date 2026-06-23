"""SIS: Susceptible <-> Infectious (no lasting immunity).

e.g. common cold. Recovery returns individuals to S; the question is endemic
persistence rather than a final epidemic size.
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SIS)
class SIS(CompartmentalModel):
    compartments = ["S", "I"]

    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        s, i = state["S"], state["I"]
        new_inf = np.minimum(params.beta * pressure * s, s)
        new_rec = np.minimum(params.gamma * i, i)
        return {"S": s - new_inf + new_rec, "I": i + new_inf - new_rec}

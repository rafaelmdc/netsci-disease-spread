"""SQIR: adds a Quarantined compartment that isolates identified cases.

e.g. Ebola, targeted outbreaks. Quarantined individuals are removed from the
*active mixing* population (N = S + I + R, excluding Q), which is what makes
isolation flatten the infectious peak relative to SIR.
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SQIR)
class SQIR(CompartmentalModel):
    compartments = ["S", "I", "Q", "R"]

    def mixing_pop(self, state: State) -> np.ndarray:
        return state["S"] + state["I"] + state["R"]  # quarantined are isolated

    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        s, i, q, r = state["S"], state["I"], state["Q"], state["R"]
        new_inf = np.minimum(params.beta * pressure * s, s)
        # quarantine first, then direct recovery from the remainder (keeps I >= 0)
        new_quar = np.minimum(params.kappa * i, i)
        new_rec_i = np.minimum(params.gamma * i, i - new_quar)
        new_rec_q = np.minimum(params.gamma_q * q, q)
        return {
            "S": s - new_inf,
            "I": i + new_inf - new_quar - new_rec_i,
            "Q": q + new_quar - new_rec_q,
            "R": r + new_rec_i + new_rec_q,
        }

"""SEIR: adds a latent Exposed compartment (infected, not yet infectious).

e.g. COVID-19, SARS. The force of infection depends on I only; Exposed
individuals carry the pathogen but do not transmit, so the E peak precedes
the I peak.
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SEIR)
class SEIR(CompartmentalModel):
    compartments = ["S", "E", "I", "R"]

    def reaction(self, state: State, params: ModelParams) -> State:
        s, e, i, r = state["S"], state["E"], state["I"], state["R"]
        n = s + e + i + r
        with np.errstate(divide="ignore", invalid="ignore"):
            force = np.where(n > 0, params.beta * i / n, 0.0)
        new_exp = np.minimum(force * s, s)
        new_inf = np.minimum(params.sigma * e, e)  # sigma validated non-None for SEIR
        new_rec = np.minimum(params.gamma * i, i)
        return {
            "S": s - new_exp,
            "E": e + new_exp - new_inf,
            "I": i + new_inf - new_rec,
            "R": r + new_rec,
        }

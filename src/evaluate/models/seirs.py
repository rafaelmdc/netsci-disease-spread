"""SEIRS: SEIR with waning immunity (R -> S at rate omega).

e.g. seasonal influenza. Recovered individuals lose immunity over ~1/omega
days and re-enter the susceptible pool, which permits recurrent waves rather
than a single self-limiting epidemic. The local reproduction number is still
R0 = beta / gamma (the E compartment delays but does not change it).
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SEIRS)
class SEIRS(CompartmentalModel):
    compartments = ["S", "E", "I", "R"]
    entry_key = "E"  # newly infected become Exposed (latent), not yet infectious

    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        s, e, i, r = state["S"], state["E"], state["I"], state["R"]
        new_exp = np.minimum(params.beta * pressure * s, s)
        new_inf = np.minimum(params.sigma * e, e)  # sigma validated non-None for SEIRS
        new_rec = np.minimum(params.gamma * i, i)
        new_wane = np.minimum(params.omega * r, r)  # omega validated non-None; R -> S
        return {
            "S": s - new_exp + new_wane,
            "E": e + new_exp - new_inf,
            "I": i + new_inf - new_rec,
            "R": r + new_rec - new_wane,
        }

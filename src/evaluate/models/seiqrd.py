"""SEIQR+D: latent period + isolation + disease death.

e.g. Ebola and other viral haemorrhagic fevers. Newly infected are Exposed
(latent) before becoming Infectious; infectious cases are either isolated
(I -> Q at kappa) or removed directly (I -> R/D at gamma). Isolation and death
both remove people from the mixing population, so the effective infectious
period is 1/(kappa + gamma) and the local reproduction number is
R0 = beta / (kappa + gamma). A case-fatality fraction ``mu`` of every removal
(from I directly, and from Q) goes to the Dead compartment; the rest recover.
``mu`` defaults to 0, which reduces this to a plain SEIQR.
"""

from __future__ import annotations

import numpy as np

from src.config import ModelName, ModelParams
from src.evaluate.models.base import CompartmentalModel, State
from src.evaluate.models.registry import MODEL_REGISTRY


@MODEL_REGISTRY.register(ModelName.SEIQRD)
class SEIQRD(CompartmentalModel):
    compartments = ["S", "E", "I", "Q", "R", "D"]
    entry_key = "E"  # newly infected become Exposed (latent), not yet infectious

    def mixing_pop(self, state: State) -> np.ndarray:
        # quarantined are isolated and the dead do not mix
        return state["S"] + state["E"] + state["I"] + state["R"]

    def reaction(self, state: State, params: ModelParams, pressure: np.ndarray) -> State:
        s, e, i, q, r, d = (state[c] for c in ("S", "E", "I", "Q", "R", "D"))
        mu = params.mu if params.mu is not None else 0.0
        new_exp = np.minimum(params.beta * pressure * s, s)
        new_inf = np.minimum(params.sigma * e, e)  # E -> I
        # isolate first, then direct removal from the remainder (keeps I >= 0)
        new_quar = np.minimum(params.kappa * i, i)
        new_rem_i = np.minimum(params.gamma * i, i - new_quar)  # I -> removed (not isolated)
        new_rem_q = np.minimum(params.gamma_q * q, q)  # Q -> removed
        die_i, die_q = mu * new_rem_i, mu * new_rem_q
        return {
            "S": s - new_exp,
            "E": e + new_exp - new_inf,
            "I": i + new_inf - new_quar - new_rem_i,
            "Q": q + new_quar - new_rem_q,
            "R": r + (new_rem_i - die_i) + (new_rem_q - die_q),
            "D": d + die_i + die_q,
        }

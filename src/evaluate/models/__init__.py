"""Compartmental models, registered by name.

Slice 0 ships SIR (the only one the walking skeleton needs). SIS/SEIR/SQIR
follow in Slice 1 using the same ``CompartmentalModel`` interface.
"""

from __future__ import annotations

from src.config import ModelName
from src.evaluate.models.base import CompartmentalModel
from src.evaluate.models.sir import SIR

_REGISTRY: dict[ModelName, type[CompartmentalModel]] = {
    ModelName.SIR: SIR,
}


def get_model(name: ModelName) -> CompartmentalModel:
    if name not in _REGISTRY:
        raise NotImplementedError(
            f"model {name.value!r} not implemented yet (Slice 1). "
            f"available: {[m.value for m in _REGISTRY]}"
        )
    return _REGISTRY[name]()

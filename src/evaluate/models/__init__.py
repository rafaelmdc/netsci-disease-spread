"""Compartmental models, discovered via the model registry.

Importing this package registers every model (each module self-registers
with ``@MODEL_REGISTRY.register(...)``), so ``get_model`` resolves any of
SIR / SIS / SEIR / SQIR.
"""

from __future__ import annotations

from src.evaluate.models import seir, sir, sis, sqir  # noqa: F401  (register on import)
from src.evaluate.models.registry import MODEL_REGISTRY, get_model

__all__ = ["MODEL_REGISTRY", "get_model"]

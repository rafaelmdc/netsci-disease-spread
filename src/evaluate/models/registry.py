"""Model factory. Each model self-registers via @MODEL_REGISTRY.register(...)."""

from __future__ import annotations

from src.config import ModelName
from src.evaluate.models.base import CompartmentalModel
from src.registry import Registry

MODEL_REGISTRY: Registry[ModelName, type[CompartmentalModel]] = Registry("model")


def get_model(name: ModelName) -> CompartmentalModel:
    return MODEL_REGISTRY.get(name)()

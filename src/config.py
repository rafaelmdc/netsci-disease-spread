"""Typed, validated experiment configuration.

A run is a pure function of its *resolved* config plus seed. The ``run_id``
is a stable hash of that config, so identical inputs map to identical
outputs (and the sweep can cache / ``-resume``). See docs/MAINTENANCE.md.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class ModelName(StrEnum):
    SIR = "sir"
    SIS = "sis"
    SEIR = "seir"
    SQIR = "sqir"


class StrategyName(StrEnum):
    CONTROL = "control"
    RANDOM = "random"
    DEGREE = "degree"
    BETWEENNESS = "betweenness"
    KCORE = "kcore"
    SUBGRAPH = "subgraph"


class Layer(StrEnum):
    AIR = "air"
    LAND = "land"
    WATER = "water"


class ModelParams(BaseModel):
    """Compartmental rates. Unused rates stay None and must be absent for
    the chosen model (validated below)."""

    beta: float = Field(gt=0, description="transmission rate")
    gamma: float = Field(gt=0, description="recovery rate")
    sigma: float | None = Field(default=None, gt=0, description="incubation rate (SEIR)")
    kappa: float | None = Field(default=None, gt=0, description="quarantine rate (SQIR)")
    gamma_q: float | None = Field(default=None, gt=0, description="recovery from quarantine (SQIR)")


class ModelConfig(BaseModel):
    name: ModelName
    params: ModelParams

    @model_validator(mode="after")
    def _check_required_rates(self) -> ModelConfig:
        p = self.params
        if self.name is ModelName.SEIR and p.sigma is None:
            raise ValueError("SEIR requires `sigma` (incubation rate)")
        if self.name is ModelName.SQIR and (p.kappa is None or p.gamma_q is None):
            raise ValueError("SQIR requires `kappa` and `gamma_q`")
        return self


class StrategyConfig(BaseModel):
    name: StrategyName
    budget: int = Field(default=15, ge=0, description="number of cities to immunise")
    coverage: float = Field(default=0.75, ge=0, le=1)
    efficacy: float = Field(default=0.85, ge=0, le=1)


class NetworkConfig(BaseModel):
    region: str = "europe"
    layers: list[Layer] = Field(default_factory=lambda: [Layer.AIR])
    # population proxy: pop(v) = p0 + degree(v) * p_route
    p0: int = Field(default=150_000, ge=0)
    p_route: int = Field(default=45_000, ge=0)
    # path to a prebuilt graphml; if None, netgen builds from data/processed
    graph_path: str | None = None


class SimConfig(BaseModel):
    horizon: int = Field(default=75, gt=0, description="days simulated")
    tau: float = Field(default=0.0002, ge=0, description="base travel rate")
    seed_size: int = Field(default=2500, ge=0, description="initial infectious seed")
    seed: int = Field(default=0, description="RNG seed; output is a pure function of it")


class RunConfig(BaseModel):
    """The complete specification of one experiment."""

    network: NetworkConfig = Field(default_factory=NetworkConfig)
    model: ModelConfig
    strategy: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(name=StrategyName.CONTROL)
    )
    sim: SimConfig = Field(default_factory=SimConfig)

    @property
    def run_id(self) -> str:
        """Stable 12-char hash of the resolved config (sorted-key JSON)."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def load_run_config(path: str | Path) -> RunConfig:
    """Load and validate a RunConfig from a YAML file."""
    with open(path) as fh:
        raw = yaml.safe_load(fh) or {}
    return RunConfig.model_validate(raw)

"""The master experiment configuration — one file to tune everything.

`experiment.yaml` at the repo root is the single source of truth: which
regions and transport-layer combinations to run, which models and their
parameters, which strategies, and the sensitivity axes. It expands to the
full grid of concrete ``RunConfig`` objects (one per cell), across every
region x layer-set x model x strategy x coverage x sensitivity x seed.

Control runs are emitted once per network/model; duplicate configs are
de-duplicated by run_id.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.config import (
    Layer,
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
    StrategyConfig,
    StrategyName,
)
from src.paths import combo_name


class Population(BaseModel):
    p0: int = 150_000
    p_route: int = 45_000


class ExperimentConfig(BaseModel):
    # --- geography & substrate ---
    regions: list[str] = Field(default_factory=lambda: ["europe"])
    layer_sets: list[list[Layer]] = Field(default_factory=lambda: [[Layer.AIR]])
    population: Population = Field(default_factory=Population)
    # --- models (which to run + their parameters) ---
    models: dict[ModelName, ModelParams]
    # --- interventions ---
    strategies: list[StrategyName] = Field(
        default_factory=lambda: [
            StrategyName.CONTROL,
            StrategyName.RANDOM,
            StrategyName.DEGREE,
            StrategyName.BETWEENNESS,
        ]
    )
    budgets: list[int] = Field(default_factory=lambda: [15])
    coverages: list[float] = Field(default_factory=lambda: [0.75])
    efficacies: list[float] = Field(default_factory=lambda: [0.85])
    # --- sensitivity axes ---
    beta_scales: list[float] = Field(default_factory=lambda: [1.0])
    taus: list[float] = Field(default_factory=lambda: [0.0002])
    horizons: list[int] = Field(default_factory=lambda: [75])
    seeds: list[int] = Field(default_factory=lambda: [0])
    seed_size: int = 2500

    def networks(self) -> list[NetworkConfig]:
        return [
            NetworkConfig(
                region=region,
                layers=layers,
                p0=self.population.p0,
                p_route=self.population.p_route,
            )
            for region in self.regions
            for layers in self.layer_sets
        ]

    def expand(self) -> list[RunConfig]:
        runs: list[RunConfig] = []
        seen: set[str] = set()
        for net in self.networks():
            for mname, params in self.models.items():
                for bscale in self.beta_scales:
                    model = ModelConfig(
                        name=mname, params=params.model_copy(update={"beta": params.beta * bscale})
                    )
                    for strat in self._strategy_grid():
                        for tau in self.taus:
                            for horizon in self.horizons:
                                for seed in self.seeds:
                                    cfg = RunConfig(
                                        network=net,
                                        model=model,
                                        strategy=strat,
                                        sim=SimConfig(
                                            horizon=horizon,
                                            tau=tau,
                                            seed_size=self.seed_size,
                                            seed=seed,
                                        ),
                                    )
                                    if cfg.run_id in seen:
                                        continue
                                    seen.add(cfg.run_id)
                                    runs.append(cfg)
        return runs

    def grouped_by_network(self) -> dict[tuple[str, str], list[RunConfig]]:
        """Runs bucketed by (region, layer-combo) so each graph loads once."""
        groups: dict[tuple[str, str], list[RunConfig]] = defaultdict(list)
        for cfg in self.expand():
            combo = combo_name([layer.value for layer in cfg.network.layers])
            groups[(cfg.network.region, combo)].append(cfg)
        return dict(groups)

    def _strategy_grid(self) -> list[StrategyConfig]:
        grid: list[StrategyConfig] = []
        for name in self.strategies:
            if name is StrategyName.CONTROL:
                grid.append(StrategyConfig(name=name, budget=0, coverage=0.0, efficacy=0.0))
                continue
            for budget in self.budgets:
                for cov in self.coverages:
                    for eff in self.efficacies:
                        grid.append(
                            StrategyConfig(name=name, budget=budget, coverage=cov, efficacy=eff)
                        )
        return grid


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    with open(path) as fh:
        raw = yaml.safe_load(fh) or {}
    return ExperimentConfig.model_validate(raw)

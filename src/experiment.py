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
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

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


class Protocol(BaseModel):
    """How the experiment is run: the full factorial grid, or the staged
    ('greedy with re-check') coordinate descent down the Europe realism ladder.

    In ``staged`` mode the comparison axes are walked sequentially instead of
    crossed all at once (see src/evaluate/staged.py): spread (all diseases,
    control) -> vaccinate (one anchor disease, every strategy) -> re-check the
    winning strategy on the other diseases. It trades the full grid's ~864 runs
    for ~140, at the cost of one stated caveat (a greedy winner, re-checked once
    rather than crossed everywhere).
    """

    mode: Literal["factorial", "staged"] = "factorial"
    # The realism ladder the epidemic stages run on (the Europe deep-dive).
    ladder_region: str = "europe"
    rungs: list[list[Layer]] = Field(
        default_factory=lambda: [
            [Layer.AIR],
            [Layer.AIR, Layer.LAND],
            [Layer.AIR, Layer.LAND, Layer.WATER],
        ]
    )
    # The disease the vaccination stage is tuned on; its winning strategy is
    # then re-checked on the others at the flagship rung.
    anchor_disease: ModelName = ModelName.SEIR
    flagship: list[Layer] = Field(
        default_factory=lambda: [Layer.AIR, Layer.LAND, Layer.WATER]
    )
    # Metric used to choose the best strategy (a summary key; lower is better).
    rank_by: str = "peak_infected"
    # Stage 4 (dose-response): budgets (number of cities vaccinated) to sweep for
    # the WINNING strategy on the flagship, answering "how many cities for a great
    # reduction?". Empty list disables the stage.
    budget_grid: list[int] = Field(default_factory=lambda: [5, 15, 30, 60, 120, 200])


class NetworkSpec(BaseModel):
    """One explicit network to build/run: a region with a specific layer set.

    Listing networks explicitly (vs the regions x layer_sets cartesian product)
    lets the substrate be *asymmetric* — e.g. air-only across every region for
    the fair cross-region comparison, but air+land+water for Europe only, where
    the ground/ferry flow data is dense enough to be defensible.
    """

    region: str
    layers: list[Layer]


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # --- geography & substrate ---
    regions: list[str] = Field(default_factory=lambda: ["europe"])
    layer_sets: list[list[Layer]] = Field(default_factory=lambda: [[Layer.AIR]])
    # Explicit network list; when given it OVERRIDES regions x layer_sets, so
    # the substrate can be asymmetric across regions (YAML key: `networks`).
    networks_spec: list[NetworkSpec] | None = Field(default=None, alias="networks")
    population: Population = Field(default_factory=Population)
    # how to walk the grid: full factorial (default) or staged coordinate descent
    protocol: Protocol = Field(default_factory=Protocol)
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
    # per-layer travel rates for multimodal runs (multiplex metapopulation);
    # None => single global tau (correct for air-only).
    tau_by_layer: dict[str, float] | None = None
    # optional in-transit transmission (refinement axis); None => off
    transit: dict[str, dict[str, float]] | None = None
    horizons: list[int] = Field(default_factory=lambda: [75])
    seeds: list[int] = Field(default_factory=lambda: [0])
    seed_size: int = 2500

    def networks(self) -> list[NetworkConfig]:
        if self.networks_spec is not None:
            pairs = [(s.region, s.layers) for s in self.networks_spec]
        else:
            pairs = [(r, ls) for r in self.regions for ls in self.layer_sets]
        return [
            NetworkConfig(
                region=region,
                layers=layers,
                p0=self.population.p0,
                p_route=self.population.p_route,
            )
            for region, layers in pairs
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
                                            tau_by_layer=self.tau_by_layer,
                                            transit=self.transit,
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

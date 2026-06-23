"""Operating-point selection.

Not calibration (we have no outbreak to fit) but its principled stand-in:
scan a parameter and find a regime where the epidemic is *informative* — it
actually takes off, reaches its peak within the horizon, and leaves room for
interventions to matter. A regime that is trivially flat (nothing spreads) or
trivially total (everyone infected at once) makes every strategy look the
same. See docs/METHODOLOGY.md.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from src.config import (
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
    StrategyConfig,
    StrategyName,
)
from src.evaluate.engine import simulate

DEFAULT_PARAMS: dict[ModelName, ModelParams] = {
    ModelName.SIR: ModelParams(beta=0.32, gamma=0.12),
    ModelName.SIS: ModelParams(beta=0.32, gamma=0.12),
    ModelName.SEIR: ModelParams(beta=0.32, gamma=0.12, sigma=0.2),
    ModelName.SQIR: ModelParams(beta=0.32, gamma=0.12, kappa=0.15, gamma_q=0.1),
}

# an operating point is "informative" if the attack rate lands in this band
# and the peak is reached before the horizon ends.
INFORMATIVE_BAND = (0.10, 0.95)


def scan_tau(
    graph: nx.DiGraph,
    model: ModelName,
    taus: list[float],
    horizon: int,
    region: str = "europe",
    seed: int = 0,
) -> list[dict]:
    """For each travel rate, report attack rate, peak day, and whether the
    peak is reached within the horizon (control strategy, no vaccination)."""
    params = DEFAULT_PARAMS[model]
    rows = []
    for tau in taus:
        cfg = RunConfig(
            network=NetworkConfig(region=region),
            model=ModelConfig(name=model, params=params),
            strategy=StrategyConfig(
                name=StrategyName.CONTROL, budget=0, coverage=0.0, efficacy=0.0
            ),
            sim=SimConfig(horizon=horizon, tau=tau, seed=seed),
        )
        res = simulate(graph, cfg)
        total = res.summary["total_population"]
        s_final = res.timeseries["S"][-1]
        infectious = np.array(res.timeseries["I"])
        peak_day = int(infectious.argmax())
        attack = 1.0 - s_final / total if total else 0.0
        lo, hi = INFORMATIVE_BAND
        rows.append(
            {
                "tau": tau,
                "attack_rate": attack,
                "peak_day": peak_day,
                "peak_reached": peak_day < horizon - 1,
                "informative": (lo <= attack <= hi) and (peak_day < horizon - 1),
            }
        )
    return rows


def recommend(rows: list[dict]) -> dict | None:
    """Pick the informative row with the largest headroom for interventions
    (highest attack rate still inside the band)."""
    ok = [r for r in rows if r["informative"]]
    return max(ok, key=lambda r: r["attack_rate"]) if ok else None

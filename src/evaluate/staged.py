"""Staged ('greedy with re-check') protocol: a small, sequential alternative to
the full factorial sweep.

Instead of crossing every comparison axis at once (~864 runs), we walk them down
the Europe realism ladder, fixing one at a time (~140 runs):

  Stage 1  SPREAD     every disease x every rung, control only.
                      -> how spread changes with realism and disease type.
  Stage 2  VACCINATE  one anchor disease x every strategy x every rung.
                      -> we READ this stage's results and pick the strategy with
                         the best (lowest) ranking metric: the vaccination winner.
  Stage 3  RE-CHECK   that winning strategy on the OTHER diseases, flagship rung.
                      -> does the winner generalise, or is it an artefact of the
                         anchor disease? The honesty check a pure greedy descent
                         would skip (and where axis interactions surface).

The interdiction (edge-closure) experiment is a separate pipeline stage.
"""

from __future__ import annotations

import pandas as pd

from src.config import StrategyName
from src.evaluate.aggregate import collect
from src.evaluate.sweep import Echo, OnRun, run_experiment
from src.experiment import ExperimentConfig, NetworkSpec
from src.paths import RESULTS


def _ladder(master: ExperimentConfig) -> list[NetworkSpec]:
    region = master.protocol.ladder_region
    return [NetworkSpec(region=region, layers=list(r)) for r in master.protocol.rungs]


def stage_spread(master: ExperimentConfig) -> ExperimentConfig:
    """All diseases across the ladder, control only (the baseline outbreaks)."""
    return master.model_copy(
        update={"networks_spec": _ladder(master), "strategies": [StrategyName.CONTROL]}
    )


def stage_vaccinate(master: ExperimentConfig) -> ExperimentConfig:
    """The anchor disease across the ladder, every strategy (the comparison)."""
    anchor = master.protocol.anchor_disease
    return master.model_copy(
        update={
            "networks_spec": _ladder(master),
            "models": {anchor: master.models[anchor]},
        }
    )


def stage_recheck(master: ExperimentConfig, winner: StrategyName) -> ExperimentConfig:
    """The winning strategy on the OTHER diseases, at the flagship rung only.
    Control is kept as the per-disease baseline so the winner's effect is
    measurable; coverage is fixed to the most adherent level (where strategy
    actually bites)."""
    anchor = master.protocol.anchor_disease
    others = {m: p for m, p in master.models.items() if m != anchor}
    flagship = NetworkSpec(
        region=master.protocol.ladder_region, layers=list(master.protocol.flagship)
    )
    return master.model_copy(
        update={
            "networks_spec": [flagship],
            "models": others,
            "strategies": [StrategyName.CONTROL, winner],
            "coverages": [max(master.coverages)],
        }
    )


def stage_dose(master: ExperimentConfig, winner: StrategyName) -> ExperimentConfig:
    """The winning strategy on the anchor disease at the flagship rung, swept
    over budget (number of cities vaccinated) at the most adherent coverage.
    Produces the dose-response curve: how many cities for a great reduction?"""
    anchor = master.protocol.anchor_disease
    flagship = NetworkSpec(
        region=master.protocol.ladder_region, layers=list(master.protocol.flagship)
    )
    return master.model_copy(
        update={
            "networks_spec": [flagship],
            "models": {anchor: master.models[anchor]},
            "strategies": [StrategyName.CONTROL, winner],
            "budgets": list(master.protocol.budget_grid),
            "coverages": [max(master.coverages)],
        }
    )


def staged_total(master: ExperimentConfig) -> int:
    """Total runs the protocol will execute (the re-check and dose counts are the
    same whichever strategy wins, so a placeholder winner gives the exact total)."""
    placeholder = StrategyName.BETWEENNESS
    total = (
        len(stage_spread(master).expand())
        + len(stage_vaccinate(master).expand())
        + len(stage_recheck(master, placeholder).expand())
    )
    if master.protocol.budget_grid:
        total += len(stage_dose(master, placeholder).expand())
    return total


def pick_winner(master: ExperimentConfig) -> tuple[StrategyName, pd.Series]:
    """Read stage 2's runs and choose the best vaccination strategy for the
    anchor disease: lowest mean ``rank_by`` at the most adherent coverage
    (where strategies diverge). Returns the winner and the full ranking."""
    df = pd.read_parquet(RESULTS / "summary.parquet")
    anchor, rank_by = master.protocol.anchor_disease.value, master.protocol.rank_by
    vacc = df[(df["model"] == anchor) & (df["strategy"] != StrategyName.CONTROL.value)]
    if vacc.empty:
        raise RuntimeError(
            f"no vaccination runs for anchor disease '{anchor}' in summary.parquet"
        )
    vacc = vacc[vacc["coverage"] == vacc["coverage"].max()]
    ranking = vacc.groupby("strategy")[rank_by].mean().sort_values()  # lower = better
    return StrategyName(ranking.index[0]), ranking


def run_staged(
    master: ExperimentConfig,
    workers: int = 4,
    maps: bool = False,
    echo: Echo = print,
    on_run: OnRun | None = None,
) -> StrategyName:
    """Run the three stages in order, letting stage 2's data choose stage 3.
    ``echo`` receives stage banners and the winner ranking; ``on_run`` (if given)
    fires per completed run for live progress."""
    anchor = master.protocol.anchor_disease
    if anchor not in master.models:
        raise ValueError(
            f"anchor disease '{anchor.value}' is not in models {list(master.models)}"
        )

    echo("STAGE 1 - spread: every disease x rung, control only")
    run_experiment(stage_spread(master), workers, maps, echo, on_run)

    echo(f"STAGE 2 - vaccinate: anchor '{anchor.value}' x every strategy x rung")
    run_experiment(stage_vaccinate(master), workers, maps, echo, on_run)
    collect(write=True)

    winner, ranking = pick_winner(master)
    echo(f"  ranking by {master.protocol.rank_by} (lower=better) at top coverage:")
    for strat, val in ranking.items():
        mark = "  <- winner" if strat == winner.value else ""
        echo(f"    {strat:12s} {val:>14,.0f}{mark}")

    echo(f"STAGE 3 - re-check: '{winner.value}' on the other diseases at the flagship")
    run_experiment(stage_recheck(master, winner), workers, maps, echo, on_run)
    collect(write=True)

    if master.protocol.budget_grid:
        echo(f"STAGE 4 - dose: '{winner.value}' across budgets "
             f"{master.protocol.budget_grid} on the flagship")
        run_experiment(stage_dose(master, winner), workers, maps, echo, on_run)
        collect(write=True)
    return winner


def run_dose(
    master: ExperimentConfig,
    workers: int = 4,
    maps: bool = False,
    echo: Echo = print,
    on_run: OnRun | None = None,
) -> StrategyName:
    """Run only the dose-response stage, reusing the winner already chosen by an
    earlier stage-2 (read from results/summary.parquet). For iterating on the
    budget sweep without re-simulating stages 1-3."""
    winner, _ = pick_winner(master)
    echo(f"DOSE: '{winner.value}' across budgets {master.protocol.budget_grid} "
         f"on the flagship")
    run_experiment(stage_dose(master, winner), workers, maps, echo, on_run)
    collect(write=True)
    return winner

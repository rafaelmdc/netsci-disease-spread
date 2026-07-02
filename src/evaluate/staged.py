"""Staged protocol: a small, sequential walk down the Europe realism ladder.

Instead of crossing every comparison axis at once (the full factorial sweep),
we walk the ladder in two stages and then dose the winners:

  Stage 1  SPREAD   every disease x every rung, control only.
                    -> how spread changes with realism and disease type
                       (the per-disease baselines).
  Stage 2  DEFEND   every disease x every (non-control) strategy x every rung.
                    -> the SYMMETRIC comparison: what defends best is read off
                       PER DISEASE TYPE, not assumed from a single anchor. The
                       earlier 'anchor + re-check' design answered the question
                       for only one disease; here every disease gets the full
                       strategy x rung grid, so 'which strategy wins for SIR vs
                       for SIS' is a direct read.
  Stage 4  DOSE     for each disease, sweep its OWN winning strategy's budget on
                    the flagship rung -> how many cities for a great reduction?
  Stage 5  INTERDICT  the EDGE-targeting complement: for each disease, close
                    flight routes (scenarios A-D) on the flagship and see whether
                    land + ferries still carry the outbreak.

This whole module is the single "get results" step; downstream scripts read
results/ to generate the paper's tables and figures.
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


def stage_defend(master: ExperimentConfig) -> ExperimentConfig:
    """Every disease x every (non-control) strategy x every rung — the symmetric
    comparison, with no anchor. Control is supplied by stage 1, so we run only
    the active strategies here and let the aggregate join them to the baselines."""
    defenses = [s for s in master.strategies if s is not StrategyName.CONTROL]
    return master.model_copy(
        update={"networks_spec": _ladder(master), "strategies": defenses}
    )


def stage_dose_one(
    master: ExperimentConfig, disease: str, winner: StrategyName
) -> ExperimentConfig:
    """One disease's winning strategy on the flagship rung, swept over budget
    (number of cities vaccinated) at the most adherent coverage. Control is kept
    as that disease's baseline so the dose-response is measured against it."""
    flagship = NetworkSpec(
        region=master.protocol.ladder_region, layers=list(master.protocol.flagship)
    )
    return master.model_copy(
        update={
            "networks_spec": [flagship],
            "models": {disease: master.models[disease]},
            "strategies": [StrategyName.CONTROL, winner],
            "budgets": list(master.protocol.budget_grid),
            "coverages": [max(master.coverages)],
        }
    )


def stage_interdiction(
    master: ExperimentConfig, k: int = 10, echo: Echo = print
) -> None:
    """Stage 5 — EDGE targeting (interdiction). The complement to the node-targeting
    defend stage: for each disease, close flight routes (scenarios A-D) and see
    whether land + ferries still carry the outbreak. We run it on BOTH the air-only
    substrate and the multimodal flagship, so the headline contrast (grounding
    flights stops it when air is the sole carrier, but barely dents the multimodal
    outbreak) is a direct, same-axis comparison. One combined interdiction_<disease>
    .parquet per disease (with a `combo` column for the substrate) lands in the
    flagship folder; per-(disease, substrate) HTML sits in each network's folder."""
    import pandas as pd

    from src.config import (
        Layer, ModelConfig, NetworkConfig, RunConfig, SimConfig, StrategyConfig,
    )
    from src.evaluate.centrality import betweenness
    from src.evaluate.interdiction import run_scenarios
    from src.netgen.graph_io import read_graphml
    from src.paths import combo_name, network_figure, processed_graph
    from src.viz.interdiction_html import interdiction_to_html

    region = master.protocol.ladder_region
    flagship_combo = combo_name([layer.value for layer in master.protocol.flagship])
    # air-only first (the single-layer counterfactual), then the multimodal flagship
    substrates = [["air"], list(master.protocol.flagship)]

    tau = master.taus[0] if master.taus else 0.0002
    horizon = master.horizons[0] if master.horizons else 210
    seed = master.seeds[0] if master.seeds else 0

    for disease, params in master.models.items():
        rows: list[dict] = []
        for layers in substrates:
            combo = combo_name(layers)
            graph = read_graphml(processed_graph(region, combo))
            betweenness(graph)  # warm the cache once
            cfg = RunConfig(
                network=NetworkConfig(
                    region=region, layers=[Layer(x) for x in layers],
                    p0=master.population.p0, p_route=master.population.p_route,
                ),
                model=ModelConfig(name=disease, params=params),
                strategy=StrategyConfig(name=StrategyName.CONTROL, budget=0, coverage=0.0, efficacy=0.0),
                sim=SimConfig(
                    horizon=horizon, tau=tau, tau_by_layer=master.tau_by_layer,
                    transit=master.transit, seed_size=master.seed_size, seed=seed,
                ),
            )
            results = run_scenarios(graph, cfg, k=k)
            interdiction_to_html(
                results,
                network_figure(region, combo, f"interdiction_{disease.value}.html"),
                title=f"Air interdiction — {region}/{combo} — {disease.value}",
            )
            rows.extend(
                {"scenario": name, "day": day, "infectious": v,
                 "region": region, "combo": combo, "model": disease.value}
                for name, r in results.items()
                for day, v in enumerate(r["infectious"])
            )
            echo(f"  [{disease.value}] {combo} scenarios (k={k}):")
            for name, r in results.items():
                echo(f"    {name:42s} peak={r['summary']['peak_infected']:,.0f}")
        ppath = network_figure(region, flagship_combo, f"interdiction_{disease.value}.parquet")
        pd.DataFrame(rows).to_parquet(ppath)
        echo(f"  [{disease.value}] wrote {ppath.name} (air + flagship)")


def staged_total(master: ExperimentConfig) -> int:
    """Total runs the protocol will execute (the dose count is the same whichever
    strategy wins, so a placeholder winner gives the exact total)."""
    total = len(stage_spread(master).expand()) + len(stage_defend(master).expand())
    if master.protocol.budget_grid:
        placeholder = StrategyName.BETWEENNESS
        for disease in master.models:
            total += len(stage_dose_one(master, disease, placeholder).expand())
    return total


def pick_winners(
    master: ExperimentConfig,
) -> dict[str, tuple[StrategyName, pd.Series]]:
    """Read the defend-stage runs and choose, FOR EACH DISEASE, the strategy with
    the best (lowest) mean ``rank_by`` at the most adherent coverage (where
    strategies diverge). Returns ``{disease: (winner, full ranking)}``."""
    df = pd.read_parquet(RESULTS / "summary.parquet")
    rank_by = master.protocol.rank_by
    winners: dict[str, tuple[StrategyName, pd.Series]] = {}
    for disease in (m.value for m in master.models):
        vacc = df[(df["model"] == disease) & (df["strategy"] != StrategyName.CONTROL.value)]
        if vacc.empty:
            continue
        vacc = vacc[vacc["coverage"] == vacc["coverage"].max()]
        ranking = vacc.groupby("strategy")[rank_by].mean().sort_values()  # lower=better
        winners[disease] = (StrategyName(ranking.index[0]), ranking)
    return winners


def run_staged(
    master: ExperimentConfig,
    workers: int = 4,
    maps: bool = False,
    echo: Echo = print,
    on_run: OnRun | None = None,
) -> dict[str, StrategyName]:
    """Run the stages in order. Stage 2 gives every disease the full strategy x
    rung grid; we then read the best defense PER DISEASE and dose each one's own
    winner. ``echo`` receives stage banners and the per-disease rankings;
    ``on_run`` (if given) fires per completed run for live progress. Returns
    ``{disease: winning strategy}``."""
    echo("STAGE 1 - spread: every disease x rung, control only")
    run_experiment(stage_spread(master), workers, maps, echo, on_run)

    echo("STAGE 2 - defend: every disease x every strategy x rung (no anchor)")
    run_experiment(stage_defend(master), workers, maps, echo, on_run)
    collect(write=True)

    winners_full = pick_winners(master)
    echo(f"  best defense per disease by {master.protocol.rank_by} (lower=better) "
         "at top coverage:")
    for disease, (winner, ranking) in winners_full.items():
        echo(f"  [{disease}]")
        for strat, val in ranking.items():
            mark = "  <- winner" if strat == winner.value else ""
            echo(f"    {strat:12s} {val:>14,.0f}{mark}")
    winners = {d: w for d, (w, _) in winners_full.items()}

    if master.protocol.budget_grid:
        for disease, winner in winners.items():
            echo(f"STAGE 4 - dose: '{disease}' / '{winner.value}' across budgets "
                 f"{master.protocol.budget_grid} on the flagship")
            run_experiment(
                stage_dose_one(master, disease, winner), workers, maps, echo, on_run
            )
        collect(write=True)

    echo("STAGE 5 - interdiction: close flight routes (A-D) per disease on the flagship")
    stage_interdiction(master, echo=echo)
    return winners


def run_dose(
    master: ExperimentConfig,
    workers: int = 4,
    maps: bool = False,
    echo: Echo = print,
    on_run: OnRun | None = None,
) -> dict[str, StrategyName]:
    """Run only the dose-response stage, reusing the per-disease winners already
    chosen by an earlier defend stage (read from results/summary.parquet). For
    iterating on the budget sweep without re-simulating stages 1-2."""
    winners = {d: w for d, (w, _) in pick_winners(master).items()}
    for disease, winner in winners.items():
        echo(f"DOSE: '{disease}' / '{winner.value}' across budgets "
             f"{master.protocol.budget_grid} on the flagship")
        run_experiment(stage_dose_one(master, disease, winner), workers, maps, echo, on_run)
    collect(write=True)
    return winners

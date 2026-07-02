# Research Roadmap — strengthening the result for grading/review

This is the prioritised plan for turning a solid, well-engineered study into one
that survives the objections a reviewer (or grader) raises first. It is separate
from [`ROADMAP.md`](ROADMAP.md), which tracks *implementation* status; this doc
tracks the *scientific* upgrades and their acceptance criteria.

Each item lists **why** it matters, the **papers** that motivate or back it, a
concrete **plan** anchored to real files, an **effort** estimate, and the
**acceptance criteria** that mark it done. Two of the five are new results
(items 2 and 5); three close credibility gaps we already admit in the paper
(items 1, 3, 4).

## Priority order

Do them in this order; each is useful on its own, and the ordering front-loads
the changes that remove the biggest objections at the lowest cost.

| # | Item | Type | Effort | Blocks a reviewer objection? |
|---|------|------|--------|------------------------------|
| 1 | Stochastic / seed ensembles + confidence bands | Credibility | Low | Yes — the single biggest one (n=1) |
| 2 | Collective-Influence + non-backtracking strategies | New result | Low–Med | Resolves the soft vaccination result |
| 3 | Network statistics + invasion-threshold reporting | Credibility | Low | Yes — we promise these in Methods |
| 4 | Mortality (deaths-averted) metric for the lethal type | Credibility | Low | Yes — peak hides CFR, we admit it |
| 5 | Vaccination-equity / geographic-concentration figure | New result | Med | No, but adds novelty + societal angle |

---

## 1. Stochastic / seed ensembles with confidence bands

**Why.** Every headline number is currently a single deterministic run
(`experiment.yaml`: `seeds: [0]`). The Discussion already claims the strategy
*ordering* is stable across seeds and rungs, but never shows it. On a spreading
process, `n = 1` with no uncertainty is the most attackable choice in the paper.
Reporting a mean with a confidence band across seeds converts an assertion into
evidence and costs almost nothing, since the engine is already a pure function of
`(config, seed)` and the sweep parallelises over seeds.

**Plan.**
- Widen `seeds` in `experiment.yaml` from `[0]` to at least `[0..19]` (20 seeds;
  bump to 50 for the final figures if runtime allows). Seeds are already drawn in
  the giant component so every run takes off.
- Aggregation: extend `src/evaluate/aggregate.py` so `summary`, `strategy_gap`,
  and the dose table carry `mean`, `std`, and a 95% interval (percentile or
  `mean ± 1.96·sem`) per configuration, not a single value.
- Figures: `src/viz` — add error bars / shaded bands to `F-spread`, `F-defense`,
  `F-dose`, and `F-interdiction`. For the strategy-gap bars, plot the
  distribution of the betweenness-minus-degree gap so its sign is visibly
  resolved from zero (this is the crux of the vaccination claim).
- If full stochastic dynamics (not just seed variation) are wanted, add a
  Bernoulli/binomial transition draw path in `src/evaluate/engine.py` behind a
  `stochastic: true` flag; seed-variation alone is enough to satisfy the
  objection, so treat true stochasticity as optional.

**Papers.** Standard practice; cite the metapopulation ensemble framing in
Balcan et al. 2009 (`balcan:multiscale`) and the invasion-threshold stochasticity
in Colizza & Vespignani 2007 (`colizza:invasion`).

**Effort.** Low. Config + aggregation + figure styling. No new science.

**Acceptance criteria.**
- Every headline figure shows a central estimate and a 95% band.
- The strategy-gap figure demonstrates the betweenness-over-degree gap is
  positive with its interval clear of zero (or honestly reports where it is not,
  e.g. air-only / US-like regions).
- One sentence in Results and the removal of the matching caveat in
  `discussion.tex` §Limitations ("single deterministic run").

---

## 2. Collective-Influence and non-backtracking immunization strategies

**Why.** The current lead result ("betweenness beats degree by ~2–5% in Europe")
is soft because Europe is US-like, so the two obvious centralities nearly
coincide. The modern immunization literature has moved past both to methods that
provably outperform degree *and* betweenness and that specifically reward the
low-degree, high-impact nodes we already highlight as anomalous gateways
(Kittilä, Ivalo). Adding them gives a genuinely new result either way:
- if Collective Influence / non-backtracking beats betweenness on the European
  multilayer network, that is a fresh, defensible finding;
- if it collapses onto degree/betweenness (because Europe is correlated/US-like),
  that is *also* a result: even the optimal-percolation strategy offers no edge in
  correlated real regions, which sharpens the degree–betweenness story.

**Plan.**
- Add two strategies to `src/evaluate/strategies/` (registered via
  `src/registry.py`, same pattern as `degree`/`betweenness`; centrality helpers
  belong in `src/evaluate/centrality.py`):
  - `collective_influence` — Morone–Makse CI: rank nodes by
    `CI_ℓ(i) = (k_i − 1) · Σ_{j ∈ ∂Ball(i,ℓ)} (k_j − 1)`, remove greedily,
    recompute. Start with radius `ℓ = 2`.
  - `nonbacktracking` — rank nodes by their contribution to the largest
    eigenvalue of the non-backtracking (Hashimoto) matrix; drop the top-budget
    nodes. `scipy.sparse.linalg.eigs` on the 2|E|×2|E| operator, or the compact
    Bethe–Hessian surrogate for speed.
- For the multilayer flagship, use the **multiplex** Collective-Influence variant
  (rank on the aggregated multilayer adjacency, or the layer-summed CI); this is
  the version built for layered substrates, which is exactly our case.
- Add both to `strategies:` in `experiment.yaml` and re-run the defend stage.
  They plug into the existing budget/coverage/efficacy machinery unchanged.

**Papers.**
- Morone & Makse 2015, *Nature* — Collective Influence via optimal percolation.
  <https://www.nature.com/articles/nature14604>
- Osat & Radicchi 2017, *Nat. Commun.* — optimal percolation on **multiplex**
  networks (the multilayer variant for our substrate).
  <https://www.nature.com/articles/s41467-017-01442-2>
- Non-backtracking node immunization (largest-eigenvalue impact), 2020.
  <https://ui.adsabs.harvard.edu/abs/2020arXiv200212309T/abstract>
- Optional, most on-topic: message-passing identification of influential
  subpopulations *in metapopulation models*. <https://arxiv.org/pdf/2112.05879>

**Effort.** Low–Medium. CI is a few dozen lines; non-backtracking needs one
sparse eigensolve. Both reuse the existing strategy/sweep plumbing.

**Acceptance criteria.**
- `netsci evaluate` runs with `strategies` including `collective_influence` and
  `nonbacktracking` on all five disease types and all three rungs.
- `F-defense` and the strategy-gap table include the two new arms.
- A clear statement in Results/Discussion of whether either beats betweenness on
  the European multilayer net, tied back to the degree–betweenness correlation.
- New references added to `references.bib` and annotated in
  [`literature-review.md`](literature-review.md).

---

## 3. Network statistics and invasion-threshold reporting

**Why.** [`METHODOLOGY.md`](METHODOLOGY.md) §5 promises, and never delivers:
measured `⟨k⟩`, `⟨k²⟩/⟨k⟩`, and assortativity per network; the position of the
travel rate `τ` relative to the global invasion threshold; and at least one
verification against an analytic limit. Delivering your own checklist is free
credibility and pre-empts "you claimed this and didn't show it".

**Plan.**
- Metrics: extend `src/evaluate/metrics/` (and/or `centrality.py`) to emit, per
  built network, `N`, `E`, `⟨k⟩`, `⟨k²⟩`, `⟨k²⟩/⟨k⟩`, degree assortativity, and
  the giant-component fraction. Write them to a `structure`/`network_stats`
  table and surface as a paper table.
- Invasion threshold: compute the Colizza–Vespignani global invasion threshold
  for the diffusive layers and report where our `tau_by_layer` sits relative to
  it (above threshold, by what margin). This is a short calculation from
  `⟨k²⟩/⟨k⟩` and the per-layer travel rate.
- Verification (item overlaps with 2): report the non-backtracking largest
  eigenvalue as the predicted SIR/percolation threshold and show a single-node
  SIR curve matches the analytic well-mixed solution, plus the SIR final-size /
  bond-percolation correspondence (Newman 2002) already named in Methods. A
  `tests/test_verification.py` already exists; extend it and lift its numbers
  into the paper.

**Papers.** Colizza & Vespignani 2007 (`colizza:invasion`);
Pastor-Satorras & Vespignani 2001 (`pastorsatorras:scalefree`) for the
`⟨k²⟩/⟨k⟩` correction; Newman 2002 (`newman:spread`) for final-size percolation.

**Effort.** Low. Mostly reporting quantities the engine already has access to.

**Acceptance criteria.**
- A per-network statistics table (`N, E, ⟨k⟩, ⟨k²⟩/⟨k⟩`, assortativity, GC%).
- One line stating `τ` sits above the invasion threshold by a stated margin.
- One verification figure or table against an analytic limit.
- The corresponding boxes ticked in `METHODOLOGY.md` §5.

---

## 4. Mortality (deaths-averted) metric for the lethal type

**Why.** The lethal SEIQRD type carries `μ ≈ 0.71`, but every result is reported
as *peak active infection*, which the Discussion admits "does not even reflect the
isolation type's high case-fatality". A modest infectious peak can still be
devastating. Reporting cumulative deaths, and deaths averted by each strategy,
makes the Ebola row mean something instead of being an also-ran with an unusually
low peak.

**Plan.**
- Engine already tracks a fatal compartment for SEIQRD
  (`src/evaluate/models/seiqrd.py`); expose cumulative deaths as an output series.
- Metrics: add `total_deaths` and `deaths_averted = deaths(control) − deaths(strategy)`
  to `src/evaluate/aggregate.py`, alongside the existing peak metric.
- Figures: one small panel (or an added column in `F-defense`) reporting deaths
  averted for SEIQRD under each strategy, at the operating-point budget.
- Keep peak as the cross-disease common currency; deaths is the type-specific
  metric that the paper explicitly flags as missing.

**Papers.** No new citation required; this is internal consistency with the
model's own `μ`. Optionally cite a filovirus CFR source when stating `μ`.

**Effort.** Low. One derived series, one metric, one panel.

**Acceptance criteria.**
- A deaths-averted number per strategy for the lethal type in Results.
- The Discussion §Limitations caveat about the peak metric hiding CFR is
  softened to "we also report deaths for the lethal type".

---

## 5. Vaccination-equity / geographic-concentration figure

**Why.** Underexplored for transport-network immunization and it closes the loop
with our anomalous-gateway finding. Betweenness-targeting concentrates protection
on a few structural bridges; does that leave the remote peripheral gateways we
identified (Kittilä, Ivalo, Lycksele, Vilhelmina) *more* exposed, and does it
concentrate protection in a handful of countries? An equity axis turns "network
science can protect us" into "network science can protect us, and here is who it
protects and who it leaves out", which is a stronger, more novel claim and a
natural societal-impact paragraph.

**Plan.**
- For each strategy's selected node set, compute a concentration measure of where
  protection lands: a Gini coefficient of vaccinated cities per country (or per
  region), and the by-country share of *averted* cases. Nodes already carry
  country/region and coordinates from `netgen`.
- Figure: a small choropleth or bar-of-shares showing the geographic
  distribution of vaccinated cities and of protection benefit under
  betweenness vs degree vs Collective Influence.
- Analysis question to answer in text: does the most *effective* rule
  (betweenness/CI) also concentrate protection most narrowly, i.e. is there an
  efficiency–equity tension on this substrate?

**Papers.**
- Fair vaccination via influence maximization, 2024.
  <https://arxiv.org/html/2403.05564>
- Balancing fairness and efficiency in dynamic vaccine allocation,
  *Sci. Rep.* 2024. <https://www.nature.com/articles/s41598-024-84027-6>

**Effort.** Medium. New per-strategy geographic aggregation + one figure; reuses
the coordinates/country metadata already on the nodes.

**Acceptance criteria.**
- A metric (Gini or top-k country share) of protection concentration per strategy.
- One equity figure and a short subsection connecting it to the gateway result.
- New references added and annotated.

---

## Suggested execution order and a done-checklist

1. [x] Widen `seeds` (→10, resumable), ensemble aggregation + confidence bands
       (item 1). Code done; 10-seed staged ensemble running; figures carry CIs.
2. [~] Implement `collective_influence` + `nonbacktracking` strategies (item 2).
       Code + unit tests written (`tests/test_strategies_extra.py`); **not yet
       run** (waiting for the ensemble to free the CPU). Remaining: run the
       tests, then add the two names to `experiment.yaml` `strategies:` and let
       the resumable sweep compute only the new arms.
3. [~] Per-network statistics (`k2_over_k`, assortativity, giant fraction) and
       the non-backtracking epidemic-threshold (`nb_eigenvalue`, `epi_threshold`)
       in `structure_table` (item 3). Code done; **not yet run**. The τ-based
       Colizza–Vespignani metapopulation invasion number is left as a smaller
       follow-up so the delivered threshold stays rigorous.
4. [~] Deaths / deaths-averted for the lethal type (item 4). Code done
       (`aggregate.deaths_table` + `figures.fig_deaths`), reading the `D`
       compartment from existing `timeseries.parquet` — **no recompute needed**.
       Not yet run.
5. [~] Equity concentration metric + figure (item 5). Code done
       (`aggregate.equity_table` + `figures.fig_equity`): per-strategy Gini and
       top-country share of the vaccinated set. Not yet run. (The cases-averted
       -by-country half waits for the ensemble results.)
6. [ ] Update `results.tex` / `discussion.tex`, remove the now-addressed caveats,
       and refresh `CHANGELOG.md` + `ROADMAP.md`.

Items 1–4 make the study *defensible*; items 2 and 5 make it *novel*. If time is
short, items 1 and 2 are the two that most move the grade.

---

## After the data lands — runbook

The 10-seed staged ensemble (item 1) is running now. The code for items 2–5 is
written but **not yet executed** (the box is busy with the sweep). Once the sweep
finishes, run the following in order. Everything except the sweep is one-shot, and
the sweep is resumable (`skip_existing`), so nothing here is wasted if interrupted.

1. **Confirm the run completed.** Tail the log and check stage 5 wrote fresh
   `results/europe/air+land+water/interdiction_<disease>.parquet` files. Count:
   `find results -name summary.json | wc -l`.

2. **Verify the new code (items 2–3), now the box is free.**
   `uv run pytest tests/test_strategies_extra.py -q`, then a full
   `uv run pytest -q` and `uv run ruff check`. These are the first executions of
   the Collective-Influence / non-backtracking code — expect to fix any small
   issues the untested code has.

3. **(Optional — gives item 2 its results) Add the two modern strategies and
   re-run.** Append `collective_influence` and `nonbacktracking` to
   `experiment.yaml`'s `strategies:` list and re-run
   `uv run netsci evaluate staged --config experiment.yaml --workers 10`. Only the
   two new arms compute (everything else is reused); `fig_defense` and the
   strategy-gap table then include them automatically.

4. **Rebuild aggregates, tables and figures:**
   - `uv run netsci evaluate collect`   → `summary.parquet` + `strategy_gap.parquet` (with 95% CI)
   - `uv run netsci evaluate structure` → `structure.parquet`: `k2_over_k`, `assortativity`, `giant_frac`, `nb_eigenvalue`, `epi_threshold` (item 3)
   - `uv run netsci viz figures`        → F-spread/defense/dose/interdiction (CIs) + F-deaths (item 4) + F-equity (item 5)
   - `uv run netsci viz tables`         → T1 and derived tables

5. **(Optional) Even the ensemble.** The first, killed 20-seed run left orphan
   seed-10..16 files for some cells, so a few have >10 seeds. For uniform CIs,
   either delete run folders with `seed >= 10` before step 4, or widen `seeds` to
   `[0..19]` and re-run to fill them in. Paired figures (defense/dose) inner-join
   on seed, so this only affects the spread/interdiction bars.

6. **Read the real numbers.** Each figure writes a CSV beside its PDF in
   `docs/curated_tex/figures/` carrying the `*_ci` columns; `structure.parquet`
   carries the network stats and thresholds. Quote from these.

7. **Update the paper (item 6).** In `results.tex` / `discussion.tex`: attach the
   95% CIs to the headline numbers; state the ordering is stable across the
   ensemble; add the deaths-averted sentence for SEIQRD and the equity finding;
   report `k2_over_k`, assortativity, and where the operating β/γ sits relative to
   the `1/nb_eigenvalue` threshold; delete the "single deterministic run" caveat
   from Limitations. If the modern strategies were run (step 3), state whether
   either beats betweenness on the European multilayer net.

8. **Housekeeping.** Add the new references (Morone & Makse, Osat & Radicchi,
   Torres et al., the fairness papers) to `references.bib`, annotate them in
   `literature-review.md`, and update `CHANGELOG.md` + this checklist.

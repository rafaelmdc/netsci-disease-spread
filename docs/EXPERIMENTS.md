# Experiment & Network Plan

What we build, what we run on it, and which paper artifact each produces. The
source of truth for every number here is [`../experiment.yaml`](../experiment.yaml);
this doc explains the *design* behind it. The guiding rule: **every network earns
its place by answering one sentence in the paper.** The cross-region networks feed
a structural table only (instant, no simulation); the full disease × strategy grid
runs only where the story needs it (the Europe realism ladder).

Central question: **In Europe, once you account for air *and* water *and* land
travel, is cheap degree-targeted vaccination as good as expensive
betweenness-targeted vaccination, and can you even stop an outbreak by grounding
flights?**

---

## 1. Networks we build (8 graphs)

The substrate is deliberately **asymmetric** (see `experiment.yaml`): air-only
everywhere for a fair cross-region comparison (uniform OpenFlights data, so
differences reflect topology, not the data source), plus the dense multimodal
stack for Europe only, where ground and ferry data is defensible.

| # | Region | Layers | Role in the paper |
|---|--------|--------|-------------------|
| 1 | **europe** | **air + land + water** | ⭐ flagship — the realistic Europe; all headline results live here |
| 2 | europe | air + water | middle rung of the realism ladder |
| 3 | europe | air | naive baseline the multilayer is compared against (shared pivot) |
| 4 | americas | air | cross-region spectrum (US-like pole) |
| 5 | asia | air | cross-region spectrum |
| 6 | africa | air | cross-region spectrum |
| 7 | oceania | air | cross-region spectrum (anomalous pole) |
| 8 | world | air | cross-region spectrum (worldwide / Guimerà pole) |

Two storylines share node **#3 (europe/air)** as their pivot:
- **Realism ladder** (#3 → #2 → #1): same region, one more layer each step
  (air → +water → +land) → shows the answer *move* as the map gets realistic.
  Water is added **before** land because land coupling is strong enough to swamp
  water's marginal effect, so we show water's contribution first.
- **Cross-region** (#3–#8): same layer (air) everywhere, fair comparison → where
  Europe sits among continents.

---

## 2. The protocol: a staged coordinate descent

Runs are driven by `protocol.mode: staged` (see `src/evaluate/staged.py`), a
sequential walk down the Europe ladder rather than a blind full-factorial. The
cross-region networks are **built** (for the topology-only region spectrum) but
get **no epidemic runs** — the funnel: wide = structure, deep = Europe.

| Stage | What it runs | Reads out |
|-------|--------------|-----------|
| **1 Spread** | every disease type × every rung, control only (no intervention) | how each disease spreads, per substrate |
| **2 Defend** | every disease × every strategy × every rung, at the operating budget | which node-targeting rule wins |
| **3 Dose** | the winning strategy's budget swept over `budget_grid` on the flagship | dose–response / diminishing returns |
| **4 Interdiction** | close routes on the air-only and the multimodal substrate | what grounding flights achieves, per substrate |

A full-factorial `mode` crossing every axis at once (the ~800-run grid) is also
available for sensitivity analysis, but the staged run is the one behind the
paper's figures. An optional `anchor_disease` can restrict stage 2 to one disease
before re-checking the winner on the rest; the current run drops the anchor and
runs the full disease × strategy grid.

---

## 3. The evaluation grid (current operating point)

Everything below comes straight from `experiment.yaml`.

| Axis | Values | Count |
|------|--------|------:|
| Disease type | SIR, SIS, SEIR, SEIRS, SEIQRD | 5 |
| Strategy | control, random, degree, betweenness, subgraph, collective-influence, non-backtracking | 7 |
| Rung (Europe) | air, air+water, air+land+water | 3 |
| Dose budgets (stage 3) | 5, 15, 30, 60, 120, 200 cities | 6 |

**Fixed** across every run so only the studied factor varies: budget = 15 cities
(stages 1–2, 4), coverage = 0.75, efficacy = 0.85, initial seed size = 2500,
horizon = 1460 days (4 years, one uniform horizon so acute and endemic types are
comparable), seeded inside the giant component so the outbreak
takes off. `tau_by_layer = {air: 0.0002, land: 0.3, water: 0.0005}`. Each
configuration is run as a ten-seed ensemble, and headline numbers carry a 95%
confidence interval across seeds.

---

## 4. The interdiction experiment (Europe, two substrates)

Removing **edges** (close routes), not **nodes** (vaccinate cities) — the
intervention only a multilayer model can express. Run on both the air-only and
the multimodal flagship substrate, for all five diseases.

| Scenario | What we do | What it shows |
|----------|-----------|---------------|
| Full | no intervention | reference outbreak (per substrate) |
| Close all air | close **all** air routes | do land + ferry carry it anyway? |
| Close top-10 hubs | close the top-10 airports by betweenness | do a few bridge closures matter? |

**Headline:** on the air-only substrate, closing all air routes collapses the
outbreak to near zero; on the multimodal substrate the same closure still leaves
32–47% of the peak standing, because land commuting and ferries keep moving
people. A single-layer model overstates a flight ban's benefit by orders of
magnitude.

---

## 5. What the paper actually shows (the artifacts)

The curated figure set (`docs/curated_tex/figures/`) centres on one figure per
stage, plus the parameter table:

1. **F-spread** — uncontrolled peak (as a fraction of population) by disease type
   and rung. Orders by dynamical class; nearly flat up the ladder. *(stage 1)*
2. **F-defense** — peak reduction per strategy at the operating budget on the
   flagship; betweenness wins for every disease. *(stage 2)*
3. **F-dose** — peak reduction vs number of cities vaccinated under the winning
   rule; diminishing returns. *(stage 3)*
4. **F-interdiction** — peak remaining after closing all air / top-10 hubs, air-only
   vs multimodal. *(stage 4)*
5. **T1** — the per-type disease parameters (paper Appendix A).

Separately, the **cross-region structural table** (ρ(deg,btw) + anomalous-gateway
count per air network) places Europe on the US-like ↔ worldwide-like spectrum,
from the topology-only pass on all eight networks.

---

## 6. Run-count budget

The staged run is roughly: stage 1 (5 diseases × 3 rungs) + stage 2 (5 × 7 × 3) +
stage 3 (6 budgets on the flagship winner) + stage 4 (5 diseases × 2 substrates ×
scenarios) — on the order of ~155 configurations, each run as a ten-seed
ensemble, for roughly 1,600 simulations in total, plus the instant structural
pass on all eight graphs. Every run maps to a figure — well under the
full-factorial grid the same axes would generate.

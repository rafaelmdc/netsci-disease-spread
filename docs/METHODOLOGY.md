# Methodology — Models & Parameter Choice

How each epidemic model is defined and, crucially, **how the parameters are
justified**. This is where a result is most easily challenged, so the guiding
principle is: *make every number traceable and make the result robust to
it.* BibTeX keys refer to [`curated_tex/references.bib`](curated_tex/references.bib).

---

## 1. How the models are used

Each model is the **reaction** half of a *metapopulation
reaction–diffusion* system (`colizza:reactiondiffusion`): a compartmental
model runs inside every node, and individuals **diffuse** along network
edges each day — the standard metapopulation two-part loop.

Per day, per node $i$:

**Reaction (local dynamics).** Force of infection
$\lambda_i = \beta \, I_i / N_i$, then the standard transitions:

| Model | Compartments | Transitions (rates) |
|-------|--------------|---------------------|
| SIR    | S, I, R          | S→I ($\lambda_i$), I→R ($\gamma$) |
| SIS    | S, I             | S→I ($\lambda_i$), I→S ($\gamma$) |
| SEIR   | S, E, I, R       | S→E ($\lambda_i$), E→I ($\sigma$), I→R ($\gamma$) |
| SEIRS  | S, E, I, R, S    | as SEIR, plus R→S ($\omega$) waning |
| SEIQRD | S, E, I, Q, R, D | S→E ($\lambda_i$), E→I ($\sigma$), I→Q ($\kappa$) / R ($\gamma$) / D ($\mu$), Q→R ($\gamma_Q$) |

**Mobility — two mechanisms (not all diffusion).** Treating every transport
layer as diffusion is a known error (`balcan:recurrent`), so we separate:

- **Diffusive (air, water).** A fraction of each compartment *relocates*
  along outbound edges per day and mixes at the destination (route weight
  $w_{ij}$ × per-layer travel rate). Standard reaction–diffusion.
- **Recurrent (land/commuting).** Commuters travel by day, mix at the
  destination, and **return home** — they are *not* relocated. We couple the
  **force of infection** instead: a city $i$'s residents feel pressure
  $\pi_i=\sum_j C_{ij}\,I^*_j/N^*_j$, where $C$ is the per-capita commuting
  matrix (land radiation kernel + stay-home diagonal) and $I^*_j,N^*_j$ are
  the infectious / total people *present* at $j$. No land ⇒ $C=I$ ⇒
  $\pi_i=I_i/N_i$ (plain diffusive). This follows the GLEAM/Balcan and
  movement-interaction-return frameworks (`sorianopanos:multiplex`).

**In-transit transmission (optional refinement axis).** By default transmission
happens only at cities. Turning on `sim.transit` lets travellers be infected
*during* the trip — most important for long confined journeys (ferries,
`rocklov:diamondprincess`). We run the model's **full reaction** on each
travelling cohort for the trip duration (`distance/speed`) at an onboard contact
rate, so passengers can be infected *and* recover/incubate/quarantine en route
(not a one-way toggle). A per-layer `control` ∈ [0,1] reduces onboard
transmission (screening, onboard quarantine, hospital ship) — this is how the
"quarantine on boats" experiments are run. Toggleable, so it is a clean
comparison axis (base vs in-transit, with vs without onboard control).

> **On the modelling choice.** Recurrent coupling is the *correct* representation of
> daily commuting: commuters return home, so they couple neighbours' force of infection
> without being relocated (`balcan:recurrent`, `sorianopanos:multiplex`). We adopt it on
> that ground, not because it swings the headline number. At our operating point the peak
> active infection is close either way, because the air layer already synchronises the
> continent and leaves the land-mobility *mechanism* a marginal correction on top. The two
> operators do differ in the expected direction when air is removed: on a land-only or
> controlled chain network, diffusion peaks higher and earlier, but the effect is modest
> (under about 20%), not a threshold-dominating swing.

Holding the dynamics fixed while only the layer set / region changes is what
makes the comparisons clean.

> **Design rule:** the *only* differences between experiments are the
> model, the strategy, the layer combination, and the seed. Everything
> else is held constant. That turns the study into a clean controlled
> comparison rather than a forecasting exercise.

> **Comparison-axis consistency (critical).** Whatever varies across a
> comparison axis must be the *only* thing that varies. In particular, the
> network **construction method must be identical for every region** — we
> cannot use Eurostat commuting flows for Europe and a model for other
> continents, or region differences would reflect the *data source*, not
> the topology, invalidating the degree–betweenness comparison. We
> therefore build land-flow weights with a single gravity/radiation model
> (`simini:radiation`) applied uniformly everywhere, and use Eurostat only
> to *validate* it within Europe. The same rule applies to any layer: one
> construction recipe across all regions.

---

## 2. How parameters are chosen — three approaches in the literature

| Approach | What you do | Used by | Pros | Cons / when wrong |
|----------|-------------|---------|------|-------------------|
| **A. Calibration / likelihood fit** | Fit $R_0$ (and seeding) by maximum likelihood to *observed* case/arrival data | GLEAM: `balcan:gleam`, `balcan:h1n1` | Gold standard; predictive | Needs a real outbreak to fit to — **we don't have one** (OpenFlights has no cases) |
| **B. Literature-anchored $R_0$** | Fix clinical rates ($\gamma,\sigma,\kappa$) from epidemiology; set $\beta$ to hit a target $R_0$ from the literature for a *named* disease | most network-simulation papers | Defensible, transparent, no fitting data needed | Absolute incidence is illustrative, not predictive |
| **C. Theoretical sweep** | Don't claim realism; sweep $\beta,\gamma$ over a grid and study regimes vs the epidemic threshold | network-physics papers (`pastorsatorras:review`) | Maps the whole phase space | Hard to tie to "measles vs COVID" narrative |

**Our choice: B as the backbone, C as the robustness check, B-honest about
not being A.** This is the most defensible position for a project on a
synthetic-population network:

1. **Anchor each model to a named disease via a literature $R_0$.** Each
   model is paired with a representative disease and cites an $R_0$ range:

   | Model | Disease archetype | Typical $R_0$ (from literature) | Fixed clinical rate |
   |-------|-------------------|-------------------------------|---------------------|
   | SIR    | measles / rubella / mumps | high (≈12–18 measles) | $\gamma$ from infectious period |
   | SIS    | gonorrhea / endemic | low, persistent | $\gamma$ from infectious period |
   | SEIR   | COVID-19 / SARS | ≈2–3 (early COVID) | $\sigma$ from incubation, $\gamma$ from infectious period |
   | SEIRS  | influenza / RSV | ≈1.3–1.8 | + $\omega$ from immunity duration |
   | SEIQRD | Ebola / Marburg | ≈1.5–2.5 | + $\kappa$ from time-to-isolation, $\mu$ from CFR |

   The exact per-type values and their sources are in the paper's parameter
   tables (Appendix A).

2. **Back $\beta$ out of $R_0$ — but on a network, not naively.** The
   well-mixed identity $R_0=\beta/\gamma$ is wrong on a heterogeneous
   graph. Two corrections to state explicitly:
   - **Degree heterogeneity:** $R_0 \propto \frac{\beta}{\gamma}\cdot
     \frac{\langle k^2\rangle}{\langle k\rangle}$, so hubs inflate $R_0$
     (`pastorsatorras:scalefree`, `pastorsatorras:review`). Our European
     grid has large $\langle k^2\rangle/\langle k\rangle$.
   - **Metapopulation invasion threshold:** even locally super-critical
     disease stays local below a critical mobility rate
     (`colizza:invasion`). So $\tau$ (travel rate) is a *parameter with a
     threshold*, not a free knob — report where we sit relative to it.
   - Compute $R_0$ for the multi-compartment models (SEIR/SEIRS/SEIQRD) with the
     **next-generation matrix** method (`vandendriessche:r0`), not by
     guessing.

3. **Sensitivity analysis (approach C as insurance).** For each model,
   sweep $\beta$ (or $R_0$), $\tau$, vaccination coverage and efficacy over
   a grid and report whether the *ranking* of strategies / layer
   combinations is stable. The headline claims must survive this sweep.
   Nextflow makes the sweep cheap (see [`ARCHITECTURE.md`](ARCHITECTURE.md)).

---

## 3. Honesty / limitations to state up front

- **Modelled flows & travel rate.** Node populations are real (GeoNames
  cities), but land-commuting flows come from a gravity/radiation model and the
  per-layer travel rate $\tau$ is assumed, not measured. ⇒ Frame the work as
  **comparative/structural**, not predictive. Our claims are about *differences*
  (strategy A vs B, layer combo A+L vs A), which are far more robust than
  absolute case counts.
- **Static network.** No timetables; a temporal extension
  (`holme:temporal`) is future work.
- **Why this is still defensible:** GLEAM-style calibration (A) is
  impossible without case data; literature-anchoring (B) + sensitivity (C)
  is the standard, reviewable alternative, and holding all non-studied
  parameters fixed isolates the effect we actually care about.

---

## 4. Are we calibrating? Calibration vs. verification

"Calibration/tuning" bundles four different things with very different
cost/return. We do **not** do epidemiological calibration, and that is the
*correct* choice here — but three calibration-adjacent steps are justified.

| What | Do we? | Why / why not | Cost · return |
|------|--------|---------------|---------------|
| **Epidemiological calibration** — fit $R_0$/$\beta$ to observed case data (GLEAM: `balcan:gleam`, `balcan:h1n1`) | **No** | There is **no ground-truth outbreak on OpenFlights to fit to.** Fitting would mean inventing a target. Predictive papers calibrate because they have surveillance data; structural/comparative papers (us, `pastorsatorras:review`, `newman:spread`) parameterise + sweep instead. | high · n/a here |
| **Operating-point selection** — choose the $R_0$ regime where strategies actually *differ* | **Yes (essential)** | If the outbreak is trivially total or trivially dies, every strategy looks identical. Pick $\beta$ so we sit in an informative regime relative to the epidemic/invasion threshold (`pastorsatorras:scalefree`, `colizza:invasion`). | ~free · high |
| **Sensitivity sweep** — show the *ranking* of strategies/combos/regions is stable across $\beta,\tau,$ coverage, efficacy | **Yes** | This is what *replaces* calibration's credibility role. Cheap because the sweep machinery already exists (`ditommaso:nextflow`). | low · high |
| **Verification against theory** — sim matches analytic limits: single-node SIR curve; threshold scaling with $\langle k^2\rangle/\langle k\rangle$; SIR final-size vs bond-percolation (`newman:spread`) | **Yes** | Not data-fitting — it validates the *implementation*. Catches bugs and is independently convincing. | low · high |
| **ML hyperparameter tuning** | only if GNN extension added (`liu:gnnreview`) | train/val/test split, search | n/a for the core study |

**Bottom line.** Hard calibration is neither possible nor justified on a
synthetic-population network; the three rows marked *Yes* recover most of
its credibility at near-zero added complexity, reusing the same sweep. The
non-negotiable one is **operating-point selection** — skip it and the
results can be accidentally trivial.

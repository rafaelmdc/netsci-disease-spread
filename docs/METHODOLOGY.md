# Methodology — Models & Parameter Choice

How we define each epidemic model and, crucially, **how we justify the
parameters**. This is the part reviewers attack first, so the guiding
principle is: *make every number traceable and make the result robust to
it.* BibTeX keys refer to [`tex/references.bib`](tex/references.bib).

---

## 1. How the models are used

Each model is the **reaction** half of a *metapopulation
reaction–diffusion* system (`colizza:reactiondiffusion`): a compartmental
model runs inside every node, and individuals **diffuse** along network
edges each day. This is exactly the blueprint's two-part loop.

Per day, per node $i$:

**Reaction (local dynamics).** Force of infection
$\lambda_i = \beta \, I_i / N_i$, then the standard transitions:

| Model | Compartments | Transitions (rates) |
|-------|--------------|---------------------|
| SIR  | S, I, R       | S→I ($\lambda_i$), I→R ($\gamma$) |
| SIS  | S, I          | S→I ($\lambda_i$), I→S ($\gamma$) |
| SEIR | S, E, I, R    | S→E ($\lambda_i$), E→I ($\sigma$), I→R ($\gamma$) |
| SQIR | S, I, Q, R    | S→I ($\lambda_i$), I→Q ($\kappa$), Q→R ($\gamma_Q$), I→R ($\gamma$) |

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

> **Why it matters (professor-facing):** on the European air+land network,
> modelling commuting as recurrent rather than diffusive lowers the peak
> active infection ~5× (~277M → ~49M) — recurrent commuting couples
> neighbours without transporting the seed population across the continent.
> This is a real, threshold-shifting effect (`balcan:recurrent`), not a tuning
> artifact, and it is why the land layer is *not* modelled as diffusion.

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

1. **Anchor each model to a named disease via a literature $R_0$.** The
   blueprint already pairs models with diseases — keep that and cite an
   $R_0$ range for each:

   | Model | Disease archetype | Typical $R_0$ (cite in paper) | Fixed clinical rate |
   |-------|-------------------|-------------------------------|---------------------|
   | SIR  | measles / smallpox | high (≈12–18 measles) | $\gamma$ from infectious period |
   | SIS  | common cold / endemic | low, persistent | $\gamma$ from infectious period |
   | SEIR | COVID-19 / SARS | ≈2–3 (early COVID) | $\sigma$ from incubation, $\gamma$ from infectious period |
   | SQIR | Ebola / targeted | ≈1.5–2.5 | + $\kappa$ from time-to-isolation |

   *(Fill the exact values and citations in Table 1 of the paper — these
   are placeholders pending the team's chosen sources.)*

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
   - Compute $R_0$ for the multi-compartment models (SEIR/SQIR) with the
     **next-generation matrix** method (`vandendriessche:r0`), not by
     guessing.

3. **Sensitivity analysis (approach C as insurance).** For each model,
   sweep $\beta$ (or $R_0$), $\tau$, vaccination coverage and efficacy over
   a grid and report whether the *ranking* of strategies / layer
   combinations is stable. The headline claims must survive this sweep.
   Nextflow makes the sweep cheap (see [`ARCHITECTURE.md`](ARCHITECTURE.md)).

---

## 3. Honesty / limitations to state up front

- **Synthetic population & travel rate.** Node population is a degree
  proxy ($P_0 + d\cdot P_\text{route}$) and $\tau$ is assumed, not
  measured. ⇒ Frame the work as **comparative/structural**, not
  predictive. Our claims are about *differences* (strategy A vs B, layer
  combo A+L vs A), which are far more robust than absolute case counts.
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
| **Verification against theory** — sim matches analytic limits: single-node SIR curve; threshold scaling with $\langle k^2\rangle/\langle k\rangle$; SIR final-size vs bond-percolation (`newman:spread`) | **Yes** | Not data-fitting — it validates the *implementation*. Catches bugs and is persuasive to reviewers. | low · high |
| **ML hyperparameter tuning** | only if GNN extension added (`liu:gnnreview`) | train/val/test split, search | n/a for the core study |

**Bottom line.** Hard calibration is neither possible nor justified on a
synthetic-population network; the three rows marked *Yes* recover most of
its credibility at near-zero added complexity, reusing the same sweep. The
non-negotiable one is **operating-point selection** — skip it and the
results can be accidentally trivial.

---

## 5. Checklist for the paper's Methods section

- [ ] State each model's compartments, transitions, and the diffusion step
      (Section "Epidemic Models").
- [ ] Table 1: per-model $R_0$, $\gamma$, $\sigma$, $\kappa$ **with
      citations** for each named disease.
- [ ] Show how $\beta$ is derived from $R_0$ including the
      $\langle k^2\rangle/\langle k\rangle$ correction.
- [ ] Report measured $\langle k\rangle$, $\langle k^2\rangle$, and the
      invasion-threshold position for $\tau$.
- [ ] State the chosen operating point (target $R_0$ regime) and why it is
      informative relative to the threshold.
- [ ] Report a sensitivity sweep showing the strategy ranking is stable.
- [ ] Report at least one verification check against an analytic limit
      (single-node SIR, or threshold scaling, or bond-percolation final size).
- [ ] One explicit paragraph: "comparative, not predictive," and why.

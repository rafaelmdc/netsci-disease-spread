# Methodology — detailed writing skeleton

Working skeleton for the paper's Methodology section. Aligns with the existing
draft in [`../tex/main.tex`](../tex/main.tex) (§Data and Network, §Models and
Parameters, §Vaccination Strategies, §Pipeline and Substrate) and the overall
narrative spine in `~/.claude/plans/eager-questing-journal.md`. Notation and
`\cite{}` keys match `../tex/references.bib`.

Diagrams live in [`diagrams/`](diagrams/) as editable `.drawio` files:
- **F1** `diagrams/F1-pipeline.drawio` — three-module pipeline overview.
- **F2** `diagrams/F2-multilayer-stack.drawio` — shared-node multilayer substrate.
- **F3** `diagrams/F3-reaction-diffusion.drawio` — per-node reaction + the two mobility mechanisms.

> **Through-line for Methods:** every choice here is in service of a *controlled
> comparison* — only model / strategy / layers / seed vary; everything else is
> held fixed. Say this once, early, then point back to it.

---

## 3.1 Network construction — the multimodal substrate
*(maps to main.tex §Data and Network; figure **F1** + **F2**)*

- **Nodes.** Airports/cities from OpenFlights `\cite{openflights}`, built with
  NetworkX `\cite{hagberg:networkx}`. Region is a *parameter* of generation
  (so Europe is the focus, other regions reuse the same recipe).
- **Layers (shared node set) — F2.**
  - *air* — OpenFlights routes, weighted by flight frequency. **Diffusive.**
  - *land* — rail/road topology (OSM + GRIP `\cite{meijer:grip}`); flow weights
    from a single gravity/radiation kernel `\cite{simini:radiation}` applied
    **uniformly to every region**. **Recurrent (commuting).**
  - *water* — OSM ferries + cargo port calls `\cite{kaluza:cargo}`. **Diffusive.**
- **The comparison-axis rule (critical, state explicitly).** One construction
  recipe for every region/layer; Eurostat commuting is used only to *validate*
  the land kernel within Europe, never as a per-region production source —
  otherwise cross-region differences would reflect the data source, not topology.
- **Population proxy.** `pop(v) = P0 + d(v)·P_route` (P0=150k, P_route=45k) as a
  fallback; real GeoNames populations used where available.
- **Static-network assumption** (no timetables/seasonality) — flagged as a limitation.
- **TODO for final draft:** report measured `N, E, ⟨k⟩, ⟨k²⟩/⟨k⟩`, assortativity
  per network (the `# TODO` already in main.tex line ~144).

## 3.2 Epidemic engine — reaction–diffusion + two mobility mechanisms
*(maps to main.tex §Metapopulation dynamics; figure **F3**)*

- **Reaction (per node, per day).** Force of infection `λ_i = β I_i / N_i`; the
  five compartmental models as the reaction half of a metapopulation
  reaction–diffusion system `\cite{colizza:reactiondiffusion}`:

  | Model | Compartments | Transitions | Disease archetype |
  |-------|--------------|-------------|-------------------|
  | SIR    | S,I,R       | S→I(λ), I→R(γ) | measles (permanent immunity) |
  | SIS    | S,I         | S→I(λ), I→S(γ) | gonorrhea (no immunity) |
  | SEIR   | S,E,I,R     | S→E(λ), E→I(σ), I→R(γ) | COVID/SARS (latency) |
  | SEIRS  | S,E,I,R,S   | +R→S(ω) on SEIR | influenza (waning immunity) |
  | SEIQRD | S,E,I,Q,R,D | S→E(λ), E→I(σ), I→Q(κ)/R(γ)/D(μ), Q→R(γ_Q) | Ebola (isolation + fatality) |

- **Disease types tested:** 5 dynamical types — immunizing/SIR, latent/SEIR, lethal-isolated/SEIQR+D,
  endemic/SIS, recurrent/SEIRS — each with example diseases + literature-sourced parameters from one
  exemplar — see [`disease-types.md`](disease-types.md).
- **Mobility is NOT all diffusion** (the key modelling claim, `\cite{balcan:recurrent}`):
  - *Diffusive (air, water)* — a fraction of each compartment relocates along
    outbound edges and mixes at the destination; carries a global invasion
    threshold `\cite{colizza:invasion}`.
  - *Recurrent (land)* — commuters mix at the destination and **return home**;
    modelled as a force-of-infection coupling
    `π_i = Σ_j C_ij I*_j / N*_j` (C = per-capita commuting matrix with stay-home
    diagonal). No land ⇒ C = I ⇒ recovers plain diffusive.
  - **Justification (not a headline swing).** Recurrent coupling is adopted on
    modelling grounds (commuters return home), not because it dominates the
    number. At our operating point the two mechanisms give very similar European
    air+land peaks (~71M recurrent vs ~73M diffusive); the air layer already
    synchronises the continent. (The retracted ~5x / 277M→49M claim does not
    reproduce and is impossible for SIR — see `../METHODOLOGY.md` §1.)
- **In-transit transmission (refinement axis).** Full reaction on each travelling
  cohort for trip duration (distance/speed), onboard contact rate, onboard-control
  ∈[0,1]; matters most for ferries `\cite{rocklov:diamondprincess}`. Toggleable.

## 3.3 Intervention strategies — whom to protect, and how
*(maps to main.tex §Vaccination Strategies; supports Results 4.4/4.5)*

- **Node targeting (vaccination)** — fixed budget 15 cities, 85% efficacy, low
  (1%) vs high (75%) coverage. Strategies: `control · random · degree · betweenness`
  + structural `subgraph` (innermost k-shells `\cite{kitsak:spreaders}` + dense
  motifs `\cite{milo:motifs}`). Vaccinated cities = immune dead-ends; no edges removed.
- **Edge targeting (interdiction)** — scenarios A–D: (A) reference; (B) close all
  air, keep land+water; (C) close all air in an air-only model; (D) close top-k by
  degree vs betweenness. B-vs-C is the multilayer-only contrast.
- **Per-model hypotheses** (state as hypotheses, not results): firebreak (SIR),
  endemic-plateau filter (SIS), layover interception (SEIR), quarantine of hubs (SEIQRD).

## 3.4 Parameterisation & protocol
*(maps to main.tex §Parameter choice + §Calibration vs verification)*

- **B-backbone, C-check.** Fix clinical rates from epidemiology; set β to a
  literature R0. Network correction: `R0 ∝ (β/γ)·⟨k²⟩/⟨k⟩`
  `\cite{pastorsatorras:scalefree}`; next-generation matrix for SEIR/SEIQRD
  `\cite{vandendriessche:r0}`. (Table 1 / `tab:params` already in main.tex.)
- **We do NOT calibrate to case data** (no ground-truth outbreak on OpenFlights).
  Instead: (i) operating-point selection, (ii) sensitivity sweep for ranking
  stability, (iii) verification vs analytic limits (single-node SIR; bond-percolation
  final size `\cite{newman:spread}`). Comparative, not predictive.
- **Metrics.** Final size, peak active infection, peak day. Averaged over seeds {0,1,2}.
- **Design rule restated.** Only model/strategy/layers/seed vary.

## 3.5 Implementation & interactive simulator
*(new subsection; figure **F9** optional screenshot)*

- Three reproducible modules — retrieve → netgen → evaluate — a run is a pure
  function of (config, seed); the full sweep is orchestrated by Nextflow
  `\cite{ditommaso:nextflow}`.
- Same engine reachable two ways: the batch Nextflow pipeline **and** a FastAPI
  dashboard that streams a run day-by-day. **Both paths emit the same `results/`
  artifacts** — so the app is a reproducibility/accessibility tool, not a separate
  result. Frame accordingly; one screenshot (F9) optional, drop if pages tight.

---

## Figure checklist (Methods)
- [ ] **F1** pipeline overview — `diagrams/F1-pipeline.drawio`
- [ ] **F2** multilayer stack — `diagrams/F2-multilayer-stack.drawio`
- [ ] **F3** reaction–diffusion loop — `diagrams/F3-reaction-diffusion.drawio`
- [ ] **T1** per-model R0/rates (exists: `tab:params` in main.tex)
- [ ] **F9** simulator screenshot (optional)

## Export note
Open each `.drawio` in [draw.io / diagrams.net](https://app.diagrams.net) (or the
VS Code "Draw.io Integration" extension), then **File → Export as → PDF/SVG** into
`../tex/` for `\includegraphics`. Keep the `.drawio` source in this folder.

# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows semantic-ish versioning while pre-1.0.

## [Unreleased]

Scientific-strengthening work from [`docs/RESEARCH-ROADMAP.md`](docs/RESEARCH-ROADMAP.md).
Code is landed; the confirming ensemble run and paper-text update are pending
(see the roadmap's "After the data lands" runbook).

### Added
- **Simulator app now covers the full pipeline and every headline result.** The
  Compare -> Aggregate tab renders the paper's **dose-response**, **deaths-averted**
  (lethal SEIQRD type) and **protection-equity** results (new Plotly builders that
  reuse `summary`/`deaths`/`equity` tables), and a new in-app **Interdiction
  (scenarios A-D)** data action generates the route-closure figure the tab embeds.
  The `aggregate` task now also builds `deaths.parquet` and `equity.parquet`.
- **Shared disease presets** (`config.DISEASE_PRESETS`): one literature-anchored
  source of truth for the five disease types, consumed by the run/study forms and
  checked against `experiment.yaml` in tests. Picking a disease auto-fills its rates.
- **Seed ensembles with 95% confidence bands** (roadmap #1): `experiment.yaml`
  now sweeps a seed ensemble; `strategy_gap` reports the degree-vs-betweenness gap
  per seed with a CI; the four curated figures draw error bars / bands.
- **Collective-Influence and non-backtracking immunization strategies**
  (roadmap #2): `collective_influence` and `nonbacktracking` in the strategy
  registry, backed by cached centrality helpers.
- **Per-network structure statistics + non-backtracking epidemic threshold**
  (roadmap #3): degree assortativity, giant-component fraction, and the
  `nb_eigenvalue` / `epi_threshold` in `structure_table`.
- **Deaths-averted metric for the lethal SEIQRD type** (roadmap #4):
  `deaths_table` + `F-deaths`, read from the existing `D` compartment (no recompute).
- **Vaccination-equity metric** (roadmap #5): `equity_table` + `F-equity`
  (per-strategy Gini and top-country share of the vaccinated set).
- **Presentation figures beyond bars**: `F-geo` (the Europe network on real
  geography, betweenness-coloured, anomalous gateways ringed, air vs multimodal),
  `F-curves` (epidemic I(t) across the realism ladder, seed-median + IQR band),
  and `F-scatter` (degree vs betweenness with gateways ringed — the visual proof
  of the degree≈betweenness overlap).
- **Appendix distribution figures**: `A-peak-dist` and `A-gap-dist` show the full
  per-seed ensemble behind the headline means.
- **Expanded network descriptors**: `characterize` now also computes density,
  average clustering, mean shortest-path length + diameter (small-world), and
  Louvain community modularity. Rendered as a compact **main-text table**
  (`T2-structure`: the epidemiologically important descriptors) plus a **full
  appendix table** (`TA-structure-full`: every descriptor), and a
  **degree-distribution figure** (`F-degdist`, CCDF log-log per rung).

### Changed
- **F-deaths is now per-capita** (deaths averted per 100k), so the whole figure
  panel shares consistent units; the interdiction figure was already normalised
  (% of full-network peak).
- Sweep runs are now **resumable** (`run_and_save(skip_existing=True)`): a
  completed `(config, seed)` is reused, not recomputed, so widening the ensemble
  or adding strategies only pays for the new cells.
- The dose stage no longer re-runs `control` at every budget (reads the stage-1
  baseline instead), removing hundreds of redundant runs.

### Fixed
- **App forms could not launch SEIQRD or SEIRS** — they omitted the required
  incubation/isolation/waning rates and failed validation — and still offered the
  legacy `sqir` model and the retired `kcore` strategy. The run and study forms now
  offer the five article diseases (correct presets auto-filled) and the paper's
  strategy set, with `sqir`/`kcore` kept in the registry but out of the UI.
- Docs corrected to the current five disease types (SIR, SIS, SEIR, SEIRS,
  SEIQRD; was "four models / SQIR"), the staged protocol, and the retracted
  recurrent-vs-diffusive "~5x" claim.

## [0.1.0] - 2026-06-23

### Added
- Three-module pipeline: `retrieve` -> `netgen` -> `evaluate`.
- Metapopulation reaction-diffusion engine with five disease types
  (SIR, SIS, SEIR, SEIRS, SEIQRD) and two mobility mechanisms
  (diffusive air/water, recurrent land commuting).
- Multimodal substrate (air / land / water) as a shared-node multilayer network,
  with region as a construction parameter (Europe plus five other regions).
- Vaccination strategies: control, random, degree, betweenness, subgraph.
- Air-interdiction experiment (scenarios A-D) and cross-region
  degree-betweenness spectrum with FDR anomalous-gateway detection.
- Interactive simulator web app (FastAPI + arq worker) streaming runs live,
  plus a static navigable results site and Gephi export.
- Nextflow-in-Docker one-command batch pipeline; 70 passing tests; docs set.

[Unreleased]: https://github.com/rafaelmdc/netsci-disease-spread/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rafaelmdc/netsci-disease-spread/releases/tag/v0.1.0

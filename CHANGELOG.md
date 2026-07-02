# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows semantic-ish versioning while pre-1.0.

## [Unreleased]

Scientific-strengthening work from [`docs/RESEARCH-ROADMAP.md`](docs/RESEARCH-ROADMAP.md).
Code is landed; the confirming ensemble run and paper-text update are pending
(see the roadmap's "After the data lands" runbook).

### Added
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

### Changed
- Sweep runs are now **resumable** (`run_and_save(skip_existing=True)`): a
  completed `(config, seed)` is reused, not recomputed, so widening the ensemble
  or adding strategies only pays for the new cells.
- The dose stage no longer re-runs `control` at every budget (reads the stage-1
  baseline instead), removing hundreds of redundant runs.

### Fixed
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

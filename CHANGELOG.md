# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows semantic-ish versioning while pre-1.0.

## [Unreleased]

### Planned
See [`docs/RESEARCH-ROADMAP.md`](docs/RESEARCH-ROADMAP.md) for the prioritised
scientific work in flight: stochastic/seed ensembles with confidence bands,
Collective-Influence and non-backtracking immunization strategies, the
network-statistics and invasion-threshold reporting, a mortality (deaths-averted)
metric for the lethal disease type, and a vaccination-equity analysis.

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

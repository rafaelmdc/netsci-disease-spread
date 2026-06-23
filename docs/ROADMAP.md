# Roadmap & Status

Living document. Tracks what exists, what's next, and open decisions.

## Status (2026-06-23)

| Area | Status |
|------|--------|
| Project blueprint | ✅ in `docs/sources/` |
| Paper draft (KDD) | ✅ `docs/tex/main.tex` compiles (4 pp.) |
| Literature review | ✅ `docs/literature-review.md` (verified refs) |
| Design docs | ✅ architecture, data, methodology |
| Implementation plan | ✅ approved (uv, city-nodes, Nextflow+Docker, ORCA) |
| Slice 0 (skeleton + Docker) | ✅ toy pipeline runs end-to-end on host and in Docker; 12 tests green |
| Simulation code | 🚧 Slice 1 (Europe/air MVP) next |

> Build proceeds as **vertical slices** (each runs end-to-end). See the
> approved plan for the full slice list; phases below mirror it.

## Phases

### Phase 0 — Foundations (done)
- [x] Convert blueprint → KDD double-column paper.
- [x] Repo-level docs + verified literature.
- [ ] Pick a license; fill author metadata in `main.tex`.

### Phase 0.5 — Scaffolding + Docker (Slice 0, done)
- [x] `pyproject.toml` (uv) + `src/` layout + pydantic config + `run_id`.
- [x] `typer` CLI; ruff + pytest config (12 tests green).
- [x] Multi-stage `Dockerfile`, `docker-compose.yml`, `nextflow.config`, CI.
- [x] Toy end-to-end walking skeleton proving the I/O contracts (host + Docker).

### Phase 1 — Core Europe / air result (MVP)
- [ ] `retrieve`: OpenFlights fetcher + provenance.
- [ ] `netgen`: Europe filter, weighted air graph, population proxy.
- [ ] `evaluate/models`: SIR, SIS, SEIR, SQIR as metapopulation R-D.
- [ ] `evaluate/strategies`: control, random, degree, betweenness.
- [ ] `evaluate/metrics`: characterization + **ρ(degree, betweenness)** and
      anomalous-gateway detection (the novelty test).
- [ ] `viz`: infection curves + Gephi export.
- [ ] First end-to-end figures for the paper.

### Phase 2 — Novelty depth
- [ ] Subgraph/core-aware targeting (k-core, motifs, graphlets).
- [ ] Sensitivity sweep (β/R₀, τ, coverage, efficacy) — show ranking is
      stable (see `METHODOLOGY.md`).
- [ ] Low (1%) vs high (75%) coverage comparison.

### Phase 2b — Interactive visualizers (**must**, graded highly)
- [ ] `pyvis` interactive network (hubs, communities, node state).
- [ ] `plotly` epidemic curves (HTML, toggle strategies).
- [ ] Geo-animated outbreak over the horizon (`pydeck`/`kepler.gl`/Leaflet).
- [ ] Combined standalone HTML dashboard per region/combination.
      See [`ARCHITECTURE.md`](ARCHITECTURE.md) § Interactive visualization.

### Phase 3 — Multimodal layers
- [ ] `retrieve`/`netgen` for land (commuting/rail) and water (ferry).
- [ ] Multilayer combinations A, L, W, A+L, A+W, L+W, A+L+W.
- [ ] Per-layer travel rates; check multilayer threshold effect.

### Phase 4 — Multi-region
- [ ] Region axis: Europe → North America, Asia, Africa, Oceania, World.
- [ ] Cross-region centrality-regime comparison (Tanaka↔Guimerà spectrum).

### Phase 5 — Stretch
- [ ] Temporal network (timetables) — `holme:temporal`.
- [ ] Learning-based forecasting baseline — `liu:gnnreview`.

## Open decisions

| # | Decision | Options | Lean |
|---|----------|---------|------|
| 1 | Workflow engine | Nextflow vs Makefile vs Python sweep | Nextflow if cluster access; Makefile fallback |
| 2 | Tanaka 2014 reference | get full citation & verify | **blocking** — needed for novelty framing |
| 3 | Per-model R₀ / rates | which literature values | fill Table 1 with cited ranges |
| 4 | Population proxy | degree-based vs real city pop (GeoNames) | start degree-based, note as limitation |
| 5 | Graphlet tooling | ORCA vs graph-tool vs networkx | decide when Phase 2 starts |

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
| Slice 0 (skeleton + Docker) | ✅ toy pipeline runs end-to-end on host and in Docker |
| Slice 1 (Europe/air MVP) | ✅ real network, 4 models, ρ(deg,btw)=0.90 |
| Slice 2 (sweep + operating-point) | ✅ experiment.yaml, parallel sweep, horizon=210 (defensible) |
| Slice 3 (subgraph/core + verify) | ✅ kcore/subgraph strategies, threshold verification |
| Slice 4 (multimodal) | 🟡 land via radiation model; water + OSM/GRIP topology = GAPS |
| Slice 5 (multi-region) | ✅ cross-region spectrum (Europe correlated → Oceania anomalous) |
| Slice 6 (viz + paper) | 🟡 comparison/spectrum plots + paper results wired; geo-anim = GAP |
| Tests | ✅ 40 passing, ruff clean |

> **Open gaps for the iterate pass:** water layer + real OSM/GRIP rail/road
> topology + Eurostat validation (Slice 4); per-layer travel rates;
> geo-animated outbreak HTML; ORCA graphlets (subgraph uses triangles for now);
> finer Nextflow per-config fan-out; exact bond-percolation final-size check.

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

### Phase 1 — Core Europe / air result (MVP, done)
- [x] `retrieve`: OpenFlights fetcher + provenance.
- [x] `netgen`: tz-prefix region filter, weighted air graph, population proxy
      (Europe = 561 nodes, 10072 edges) via a layer-builder registry.
- [x] `evaluate/models`: SIR, SIS, SEIR, SQIR (registry) as metapopulation R-D,
      with a universal inert `V` compartment for correct immunization.
- [x] `evaluate/strategies`: control, random, degree, betweenness (registry).
- [x] `evaluate/metrics`: characterization + **ρ(degree, betweenness)** and
      anomalous-gateway detection.
- [x] `viz`: interactive HTML network + curves (Europe rendered).
- [ ] First paper figures + fill Table 1 (Slice 6).

> **First real result:** Europe air ρ(degree, betweenness) ≈ **0.90** with
> ~9 anomalous gateways (e.g. Kittilä, Isles of Scilly, Newquay) — high
> correlation (US-like) but with worldwide-like peripheral gateways.
> **Science fix:** betweenness is computed **unweighted** (edge `weight` is
> flight frequency, not a distance).

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

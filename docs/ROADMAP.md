# Roadmap & Status

Living document. Tracks what exists, what's next, and open decisions.

## Status (2026-06-24)

| Area | Status |
|------|--------|
| Project blueprint | ✅ in `docs/sources/` |
| Paper draft (KDD) | ✅ `docs/tex/main.tex` compiles (4 pp.) |
| Literature review | ✅ `docs/literature-review.md` (verified refs; Tanaka→Sun fixed) |
| Design docs | ✅ architecture, data, methodology, experiments, visualization |
| Slice 0 (skeleton) | ✅ toy pipeline runs end-to-end |
| Slice 1 (Europe/air MVP) | ✅ real network, 4 models, ρ(deg,btw)≈0.89 |
| Slice 2 (sweep + operating-point) | ✅ experiment.yaml (8 networks), parallel sweep, horizon=210 |
| Slice 3 (subgraph/core + verify) | ✅ subgraph strategy, threshold verification |
| Slice 4 (multimodal) | 🟡 air+land+water built for Europe; water + OSM/GRIP global coverage = GAPS |
| Slice 5 (multi-region) | ✅ cross-region spectrum (FDR anomalous-gateway detection) |
| Slice 6 (viz + explorer) | ✅ animated map, structure, panels, interdiction, navigable site, **one-tab Dash app** |
| Air-interdiction experiment | ✅ scenarios A–D (`netsci evaluate interdiction`) |
| Tests | ✅ 70 passing, ruff clean |

> **Open gaps:** real OSM/GRIP rail/road topology + Eurostat validation (land
> currently radiation-model); ORCA graphlets (subgraph uses k-core/triangles);
> running the full cross-region sweep (only Europe graphs built so far);
> refreshing paper Table 1 on the corrected networks.

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

> **First real result:** Europe air ρ(degree, betweenness) ≈ **0.89** with
> a handful of FDR-significant anomalous gateways (e.g. Kittilä, Ivalo,
> Lycksele, Vilhelmina) — high correlation (US-like) but with worldwide-like
> remote peripheral gateways.
> **Science fix:** betweenness is computed **unweighted** (edge `weight` is
> flight frequency, not a distance).

### Phase 2 — Novelty depth
- [ ] Subgraph/core-aware targeting (k-core, motifs, graphlets).
- [ ] Sensitivity sweep (β/R₀, τ, coverage, efficacy) — show ranking is
      stable (see `METHODOLOGY.md`).
- [ ] Low (1%) vs high (75%) coverage comparison.

### Phase 2b — Interactive visualizers (**must**, graded highly) — done
- [x] `pyvis` interactive network (geographic layout, vaccinated nodes).
- [x] `plotly` epidemic curves (HTML).
- [x] Geo-animated outbreak over the horizon (`plotly` geo, play + slider).
- [x] Navigable co-located static site (`netsci viz site`) + **one-tab Dash
      explorer** (`netsci viz app`) that builds its own tables on launch.
      See [`VISUALIZATION.md`](VISUALIZATION.md).

### Phase 3 — Multimodal layers
- [ ] `retrieve`/`netgen` for land (commuting/rail) and water (ferry).
- [ ] Multilayer combinations A, L, W, A+L, A+W, L+W, A+L+W.
- [ ] Per-layer travel rates; check multilayer threshold effect.

### Phase 4 — Multi-region
- [ ] Region axis: Europe → North America, Asia, Africa, Oceania, World.
- [ ] Cross-region centrality-regime comparison (Sun↔Guimerà spectrum).

### Phase 5 — Stretch
- [ ] Temporal network (timetables) — `holme:temporal`.
- [ ] Learning-based forecasting baseline — `liu:gnnreview`.

## Open decisions

| # | Decision | Options | Lean |
|---|----------|---------|------|
| 1 | Workflow engine | Nextflow vs Python sweep | ✅ local `typer` sweep implemented; Nextflow optional |
| 2 | ~~Tanaka 2014 reference~~ | ✅ **resolved** — replaced by verified Sun, Hu & Zhu (2023), `sun:anomalous` | done |
| 3 | Per-model R₀ / rates | which literature values | fill Table 1 with cited ranges |
| 4 | Population proxy | degree-based vs real city pop (GeoNames) | start degree-based, note as limitation |
| 5 | Graphlet tooling | ORCA vs graph-tool vs networkx | decide when Phase 2 starts |

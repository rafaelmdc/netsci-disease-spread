# Architecture

How the pipeline is organised and why. The experiment design is in
[`EXPERIMENTS.md`](EXPERIMENTS.md) and the outputs in
[`VISUALIZATION.md`](VISUALIZATION.md).

## Three-module pipeline

The pipeline is three stages with clean contracts between them. Stage 2
emits **every combination** of transport layers (air, land, water), so the
pipeline outputs *X standard networks* and Stage 3 produces *X
evaluations* — making layer combinations a first-class, comparable axis.

```
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
 │ 1. DATA RETRIEVAL    │   │ 2. NETWORK GENERATION│   │ 3. EVALUATION        │
 │ src/retrieve         │──▶│ src/netgen           │──▶│ src/evaluate         │
 │                      │   │                      │   │                      │
 │ per modality:        │   │ standardise each     │   │ for each network:    │
 │  • air  (OpenFlights)│   │ layer to a common    │   │  • epidemic models   │
 │  • land (rail/road/  │   │ node set, then emit  │   │   SIR/SIS/SEIR/    │
 │    commuting)        │   │ ALL combinations:    │   │  SEIRS/SEIQRD       │
 │  • water(ferry/ship) │   │  A, L, W,            │   │  • vaccination strat. │
 │                      │   │  A+L, A+W, L+W,      │   │    rand/deg/btw/      │
 │ → data/raw/<layer>   │   │  A+L+W               │   │    subgraph           │
 │   + PROVENANCE.txt   │   │ → multilayer graphs  │   │  • structural metrics │
 │                      │   │   data/processed/    │   │    gateways (FDR),    │
 │                      │   │   *.graphml          │   │    ρ(deg,btw)         │
 │                      │   │ (the X networks)     │   │ → results/ (X evals)  │
 └──────────────────────┘   └──────────────────────┘   └──────────────────────┘
                                                                  │
                                                                  ▼
                                                          plots + Gephi export
```

## Module contracts (`src/`)

| Stage / module | Responsibility | Output contract | Key deps |
|----------------|----------------|-----------------|----------|
| **1. `retrieve`** | Pull raw data per modality (air/land/water), record provenance. One sub-fetcher per source; **idempotent** (skips an already-cached source, `--force` to refetch). | `data/raw/<layer>/` + `PROVENANCE.txt` | `urllib` (stdlib); Overpass API for ferries |
| **2. `netgen`** | Filter to a **region**, map each layer onto a shared node set, weight edges, assign populations, then emit **every layer combination** as a tagged multilayer graph | `data/processed/<region>/<combo>.graphml` (the *X networks*) | `networkx` |
| **3. `evaluate`** | For each network: run epidemic models, vaccination strategies, structural metrics, and the air-interdiction experiment; aggregate to study tables | `results/<region>/<combo>/<label>/{summary.json,timeseries.parquet}` + `summary`/`strategy_gap`/`structure` parquet | `numpy`, `networkx` |
| `viz` (shared) | Interactive standalone HTML + Plotly figure builders + the navigable static site | co-located `*.html` under `results/` + `netsci viz site` | `pyvis`, `plotly` |
| `dashboard` | The **simulator web app**: design → run live → explore (the interactive front end, see below) | `netsci dashboard` (+ `netsci worker`) | `fastapi`, `arq`, `redis`, `jinja2` |

### Why this shape

- **Layers are data, combinations are the experiment.** Adding a modality
  is a new fetcher in Stage 1 + a standardiser in Stage 2; Stage 3 is
  untouched. The combination set is generated, not hand-listed.
- **One node set, many edge layers.** Every layer maps to the same
  cities/regions so combinations are just edge-set unions with per-layer
  travel rates — the multilayer metapopulation form (see literature
  review § 2b, 3b). Never merge layers into one untagged edge set.
- **Evaluation is layer-agnostic.** The compartmental dynamics
  (metapopulation reaction–diffusion) and the strategies don't know or
  care which layers are present, so the *same* code scores `A`, `A+L`, and
  `A+L+W`. That is what makes the combinations directly comparable.
- **Region is just a filter, not new code.** Europe is the primary focus,
  but `netgen` takes a `--region` argument (`europe`, `north_america`,
  `asia`, `africa`, `oceania`, `world`). Adding a continent is one filter,
  not a new module. **And it doubles as science:** running multiple regions
  directly tests the novelty question — Guimerà's *worldwide* network shows
  anomalous (degree ≠ betweenness) centrality, while the *US* network is
  reported correlated (degree ≈ betweenness). So the region axis maps onto
  the centrality-regime spectrum, with Europe as the empirical question this
  project answers.

## Stack & node identity

**Stack:** Python 3.12, `uv` (lockfile), `pydantic` configs, `typer` CLIs,
`networkx`/`numpy`/`pandas`, `pyvis`/`plotly` for HTML viz, `fastapi`+`arq`
(Redis) for the simulator web app, `pytest`/`ruff`. The whole three-module
pipeline is
orchestrated by **Nextflow inside the project Docker image** (`make run` —
see "Orchestrating the sweep" below); the grid itself is fanned out *within*
the `evaluate sweep` stage by an in-process thread pool (`concurrent.futures`).
A no-Docker `nextflow -profile local` path and the bare `netsci` CLI remain
supported for development.

**Node identity (canonicalization).** Combining layers requires a shared
node set, so nodes are keyed by **city/place** (real GeoNames cities), not by
airport. Airports map onto a place by **curated served-city first**: we use
OpenFlights' human-curated `city` label (all five London airports say
"London") and resolve that name to a GeoNames node — authoritative for ~93% of
air traffic. The geometric **gravity catchment basin** (GLEAM-style; Balcan &
Vespignani 2009 — assign the city maximising `population / max(distance, 10 km)`
within a 60 km basin) is the *fallback* for unresolvable labels and the only
route for label-less layers (OSM ferry terminals). Nearest-city snapping, which
fragmented metro hubs across suburb nodes, is a correctness bug, not a style
choice (`scripts/validate_snap.py` validates the mapping). Node attributes:
`id, name, country, region, lat, lon, population`.

**Canonical formats:** networks as `GraphML` (portable, Gephi-readable;
optional `.gpickle` cache); run outputs as `JSON` (summary + metadata) plus
`parquet` (per-day time series); visuals as standalone `HTML` (+ `GEXF`).
Each run lands in its own human-readable folder,
`results/<region>/<combo>/<label>/{summary.json,timeseries.parquet}`, where
`label` is `<model>_<strategy>_cov<coverage>_seed<seed>_<run_id[:6]>`. Every
run is also identified by a `run_id` = hash of its resolved config, so a run
is a pure function of `(config, seed)`.

## Design principles

- **One graph, swappable dynamics.** The network substrate is built once
  and reused; each model is a pure function `state_t → state_{t+1}`. Keeps
  comparisons fair.
- **Strategy = node-selection function.** Every vaccination strategy has
  the same signature `(graph, budget, **params) -> set[node]`, so adding a
  new one (e.g. acquaintance immunization) is a single file.
- **Config-driven runs.** One YAML in `configs/` fully specifies a run
  (model, params, strategy, coverage, seed). No magic numbers in code.
- **Determinism.** Every run takes an explicit RNG seed; results are a
  pure function of `(config, seed)`.

## Orchestrating the sweep

The experiment is a **staged** walk down the Europe realism ladder — `{5 disease
types} × {7 strategies} × {rungs} × {dose budgets}` at a single operating
coverage and a seed ensemble, plus the topology-only pass on the cross-region air networks
(see [`EXPERIMENTS.md`](EXPERIMENTS.md)). A `factorial` mode crossing every axis
at once is also available. Either way the jobs are independent and embarrassingly
parallel. Two layers of orchestration:

1. **Within a stage** — `netsci evaluate sweep` groups runs by network so each
   graph (and its cached betweenness) loads once, then fans the runs out over a
   thread pool (`concurrent.futures`). This is where the grid actually runs.
2. **Across the three modules** — **Nextflow** (`workflow/main.nf`) chains
   `retrieve → netgen → sweep → collect/structure → {interdiction, site}` as a
   DAG, each process running inside the project Docker image. This is the
   supported **one command**:

   ```bash
   make run                              # docker compose build + nextflow run -ansi-log true
   # equivalently:
   nextflow run workflow/main.nf         # docker is the default profile
   nextflow run workflow/main.nf -profile local   # no Docker, active env
   ```

   Params (override with `--name value`, or `make run NFARGS="…"`):
   `--config` (the grid, default `experiment.yaml`), `--interdiction` (scenario
   config), `--maps` (record per-node history for the animated maps; default
   `true`, ≈2 GB / ≈50 min — set `false` for a fast pass).

Why this path:

- **Self-contained + portable:** the only host prerequisites are Docker and
  Nextflow (no local Python). `nextflow.config` bind-mounts the host
  `data/`/`results/`/`figures/`/`vendor/` into `/app` (where `src/paths.py`
  resolves them), so every stage shares state and outputs land on the host,
  owned by the host user. The same `workflow/main.nf` runs on a cluster via the
  `cluster` profile without code changes. See `ditommaso:nextflow`.
- **Parallelism + caching:** the in-stage thread pool parallelises the grid;
  Nextflow `-resume` skips already-completed stages.
- **Provenance:** each process records inputs/outputs and Nextflow writes a
  timestamped `report-*.html` + `dag-*.html` per run.
- **No flaky downloads:** the water layer's ferry data ships as a vendored
  snapshot (`vendor/ferries_world.json`), so a clean-clone run never depends on
  a live Overpass query (see [`DATA.md`](DATA.md)).

## Interactive visualization

Interactive, browser-based visuals are a first-class output. `viz`
emits self-contained **HTML** + Plotly figure builders; the **simulator web app**
(`src/dashboard`) reuses those builders as its results views. Implemented
outputs (full detail in [`VISUALIZATION.md`](VISUALIZATION.md)):

| Output | Module | Shows |
|--------|--------|-------|
| Interactive network | `network_html.py` (pyvis) | hubs on a geographic layout, vaccinated nodes |
| Epidemic curves | `curves_html.py` (plotly) | compartment time series, hover/zoom |
| Animated outbreak map | `spread_html.py` (plotly geo) | infection spreading across the map, play button + day slider |
| Degree–betweenness structure | `structure_html.py` | per-node degree vs betweenness, anomalous gateways flagged |
| Strategy / region comparison | `compare_html.py` | strategy panel, region spectrum |
| Air-interdiction | `interdiction_html.py` | scenarios A–D (close flights, watch land/water carry it) |
| **Simulator app** | `src/dashboard` (FastAPI) | design a run, watch it stream **live day-by-day** (SSE), explore + continue ("add days") |

The simulator is a thin control plane: FastAPI enqueues an **arq** job (Redis),
the worker runs the same `src.evaluate` engine with a per-day `progress` callback
that publishes to Redis, and the dashboard relays it to the browser over SSE. It
**reuses the `viz` figure builders verbatim** (the science/plots are unchanged) —
only the shell is rebuilt. See [`VISUALIZATION.md`](VISUALIZATION.md).

Conventions: standalone HTML outputs are written **inside the run/network folder
they describe** (no separate `figures/` tree), referencing one shared
`plotly.min.js` at the results root. Each level has an `index.html`
(`netsci viz site`). Node coordinates make every network view a real map;
`.gexf`/GraphML export stays for Gephi figures.

## Multimodal substrate

The substrate is a generic weighted graph, so **air, ground (rail/road), and
sea (ferry/shipping)** layers enter as extra edge sets on a shared node set —
see [`DATA.md`](DATA.md) for the sources and how they combine into the
multilayer network.

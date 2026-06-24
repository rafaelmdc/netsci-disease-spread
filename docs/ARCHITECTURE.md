# Architecture

How the pipeline is organised and why. The design below is **implemented**;
status and remaining gaps are tracked in [`ROADMAP.md`](ROADMAP.md), the
experiment design in [`EXPERIMENTS.md`](EXPERIMENTS.md), and the outputs in
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
 │  • land (rail/road/  │   │ node set, then emit  │   │    SIR/SIS/SEIR/SQIR  │
 │    commuting)        │   │ ALL combinations:    │   │    (metapop. R-D)     │
 │  • water(ferry/ship) │   │  A, L, W,            │   │  • vaccination strat. │
 │                      │   │  A+L, A+W, L+W,      │   │    rand/deg/btw/      │
 │ → data/raw/<layer>   │   │  A+L+W               │   │    subgraph           │
 │   + PROVENANCE.txt   │   │ → multilayer graphs  │   │  • structural metrics │
 │                      │   │   data/processed/    │   │    k-core, motifs,    │
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
| **1. `retrieve`** | Pull raw data per modality (air/land/water), record provenance. One sub-fetcher per source. | `data/raw/<layer>/` + `PROVENANCE.txt` | `pandas`, `requests`, `osmnx` |
| **2. `netgen`** | Filter to a **region**, map each layer onto a shared node set, weight edges, assign populations, then emit **every layer combination** as a tagged multilayer graph | `data/processed/<region>/<combo>.graphml` (the *X networks*) | `networkx` |
| **3. `evaluate`** | For each network: run epidemic models, vaccination strategies, structural metrics, and the air-interdiction experiment; aggregate to study tables | `results/<region>/<combo>/<label>/{summary.json,timeseries.parquet}` + `summary`/`strategy_gap`/`structure` parquet | `numpy`, `networkx` |
| `viz` (shared) | Interactive standalone HTML **and a one-tab Dash explorer** (graded deliverable, see below) | co-located `*.html` under `results/` + `netsci viz app` | `pyvis`, `plotly`, `dash` |

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
  the centrality-regime spectrum, with Europe as the open question. Start
  with `europe`; the rest is `-resume` away once the pipeline is solid.

## Stack & node identity

**Stack:** Python 3.12, `uv` (lockfile), `pydantic` configs, `typer` CLIs,
`networkx`/`numpy`/`pandas`, `pyvis`/`plotly` for HTML viz, `dash` for the
interactive explorer, `pytest`/`ruff`. A local `typer` sweep
(`concurrent.futures`) is the supported orchestrator; `Dockerfile` and
`nextflow.config` are optional scaffolding for cluster runs.

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
  new one (e.g. acquaintance immunization, k-core) is a single file.
- **Config-driven runs.** One YAML in `configs/` fully specifies a run
  (model, params, strategy, coverage, seed). No magic numbers in code.
- **Determinism.** Every run takes an explicit RNG seed; results are a
  pure function of `(config, seed)`.

## Orchestrating the sweep

The experiment is `{8 networks} × {4 models} × {5 strategies} ×
{coverage levels} × {seeds}` — many independent, embarrassingly parallel jobs
(see [`EXPERIMENTS.md`](EXPERIMENTS.md)). The **implemented** orchestrator is
`netsci evaluate sweep`: it groups runs by network so each graph (and its
cached betweenness) loads once, then fans the runs out over a thread pool.
`Nextflow`/`Docker` remain optional for cluster-scale runs; the rationale for
that path:

- **Parallelism + caching:** Nextflow runs independent simulations
  concurrently and `-resume` skips completed ones.
- **Provenance:** each process records inputs/outputs; the DAG is the
  experiment definition.
- **Portability:** the same `workflow/main.nf` runs locally now and on a
  cluster/container later without code changes. See
  `ditommaso:nextflow` in the literature review.

A plain `Makefile` or a Python `multiprocessing` sweep is an acceptable
lighter-weight fallback if Nextflow proves heavy for the course timeline —
see [`ROADMAP.md`](ROADMAP.md) for the decision.

## Interactive visualization (graded deliverable)

Interactive, browser-based visuals are an explicit grading criterion. `viz`
emits self-contained **HTML** and a **one-tab Dash explorer**. Implemented
outputs (full detail in [`VISUALIZATION.md`](VISUALIZATION.md)):

| Output | Module | Shows |
|--------|--------|-------|
| Interactive network | `network_html.py` (pyvis) | hubs on a geographic layout, vaccinated nodes |
| Epidemic curves | `curves_html.py` (plotly) | compartment time series, hover/zoom |
| Animated outbreak map | `spread_html.py` (plotly geo) | infection spreading across the map, play button + day slider |
| Degree–betweenness structure | `structure_html.py` | per-node degree vs betweenness, anomalous gateways flagged |
| Strategy / region comparison | `compare_html.py` | strategy panel, region spectrum |
| Air-interdiction | `interdiction_html.py` | scenarios A–D (close flights, watch land/water carry it) |
| **One-tab explorer** | `app.py` (Dash) | all of the above, browseable; builds its tables on launch |

Conventions: outputs are **standalone `.html`** written **inside the run/network
folder they describe** (no separate `figures/` tree), referencing one shared
`plotly.min.js` at the results root so files stay small and offline. Each level
has an `index.html` (`netsci viz site`); the Dash app (`netsci viz app`) is the
interactive shell over the same precomputed data. Node coordinates make every
network view a real map; `.gexf`/GraphML export stays for Gephi figures.

## Multimodal substrate (planned extension)

The substrate is deliberately a generic weighted graph so that **air,
ground (rail/road), and sea (ferry/shipping)** layers can be added as
extra edge sets — see [`DATA.md`](DATA.md) for candidate sources and
[`ROADMAP.md`](ROADMAP.md) for how they enter as a multilayer network.

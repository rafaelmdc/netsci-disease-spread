# Architecture

How the pipeline is organised and why. This is the **intended** design;
implementation status is tracked in [`ROADMAP.md`](ROADMAP.md).

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
| **3. `evaluate`** | For each network: run epidemic models, vaccination strategies, and structural metrics; emit one record per (network × model × strategy) | `results/<combo>/<run>.json` (the *X evaluations*) | `numpy`, `networkx` |
| `viz` (shared) | Static plots **and interactive HTML** (graded deliverable, see below) | `figures/`, `*.gexf`, `*.html` | `matplotlib`, `pyvis`, `plotly`, `pydeck`/`kepler.gl` |

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

## Why Nextflow for the sweep

The experiment is a Cartesian product:
`{regions} × {≤7 layer combinations} × {4 models} × {4 strategies} ×
{coverage levels} × {seeds}`. That is many independent, embarrassingly
parallel jobs that must be reproducible and re-runnable without redoing
finished work. Stage 2 emits the networks; Nextflow fans Stage 3 out over
them.

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

Interactive, browser-based visuals are an explicit grading criterion, so
`viz` must emit self-contained **HTML**, not only static figures. Planned
outputs, cheapest → richest:

| Output | Tool | Shows |
|--------|------|-------|
| Interactive network | `pyvis` (NetworkX → HTML/vis.js) | hubs, communities, vaccinated nodes, node state colouring |
| Epidemic curves | `plotly` (HTML) | compartment time series with hover/zoom; toggle strategies |
| Geo-animated outbreak | `pydeck`/`kepler.gl` or Leaflet+D3 | infection spreading across the map over the 75-day horizon |
| Strategy/region comparison | `plotly` small-multiples | curves per strategy, per layer combination, per region |

Conventions: outputs are **standalone `.html`** (no server needed) written
to `figures/<region>/<combo>/`, one per run plus a combined dashboard, so
they can be opened directly or embedded. Gephi `.gexf` export stays for the
static, high-control figures that go in the paper.

## Multimodal substrate (planned extension)

The substrate is deliberately a generic weighted graph so that **air,
ground (rail/road), and sea (ferry/shipping)** layers can be added as
extra edge sets — see [`DATA.md`](DATA.md) for candidate sources and
[`ROADMAP.md`](ROADMAP.md) for how they enter as a multilayer network.

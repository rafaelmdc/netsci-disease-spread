# netsci-disease-spread

Simulating infection models and topology-aware vaccination strategies on
transport networks — starting with European air travel and extending to
multimodal (air / land / water) substrates and every world region.

> **Status:** early research project (MSc Network Science coursework).
> The repository currently contains the project blueprint, the paper draft,
> and design documentation. The simulation code described below is the
> intended layout and is being implemented — see [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What this is

We model how an epidemic spreads across a transport network and test which
vaccination strategy contains it best. The primary substrate is the
European subgraph of the [OpenFlights](https://openflights.org/data.html)
air network (airports = nodes, routes = weighted edges), with **land**
(rail/road/commuting) and **water** (ferry/shipping) layers added as a
shared-node multilayer network, and the **region** as a parameter so the
same analysis runs across continents and the whole world. On each network
we run four compartmental dynamics — **SIR, SIS, SEIR, SQIR** — as a
metapopulation reaction–diffusion process, and compare vaccination by
**random**, **degree**, and **betweenness** targeting (plus a structural
subgraph/core refinement). Results are delivered as interactive,
browser-based HTML visualisations, and the whole pipeline runs in Docker
for one-command reproducibility.

The accompanying paper is in [`docs/tex/`](docs/tex/) (KDD Explorations
double-column format). Background and the annotated reading list are in
[`docs/literature-review.md`](docs/literature-review.md), with a full
documentation index at [`docs/README.md`](docs/README.md).

## Research questions

1. How does vaccination affect the infected network across different
   infection models and disease parameters?
2. **(Primary novelty)** Where does Europe sit on the degree–betweenness
   spectrum — US-like (the two centralities correlate, so degree- and
   betweenness-targeted immunisation coincide) or worldwide-like (anomalous
   low-degree/high-betweenness gateways, so the strategies diverge)? The
   region parameter lets us answer this by direct cross-region comparison.
3. Can local structure — `k`-cores, motifs, graphlet signatures — refine
   *targeting* and *explain* model–strategy outcomes beyond node-level
   centrality?

## Intended repository layout

```
.
├── data/                  # raw + processed network data (git-ignored; see docs/DATA.md)
│   ├── raw/               # OpenFlights dumps, unmodified
│   └── processed/         # European subgraph, weighted graph artifacts
├── src/
│   ├── retrieve/          # MODULE 1: pull raw data per layer (air/land/water)
│   ├── netgen/            # MODULE 2: standardise layers → emit all combinations
│   ├── evaluate/          # MODULE 3: epidemic models + strategies + metrics
│   │   ├── models/        #   SIR / SIS / SEIR / SQIR (metapopulation R-D)
│   │   ├── strategies/    #   vaccination targeting (random, degree, betweenness, subgraph)
│   │   └── metrics/       #   k-core, motifs, graphlets, ρ(degree, betweenness)
│   └── viz/               # plots + Gephi export (shared)
├── workflow/              # Nextflow pipeline orchestrating the sweep (see docs/ARCHITECTURE.md)
├── configs/               # experiment parameter sets (one file per run)
├── results/              # simulation outputs (git-ignored)
├── notebooks/             # exploratory analysis
└── docs/                  # paper, literature review, design docs
```

The pipeline is **three modules** — *data retrieval → network generation →
evaluation* — where network generation emits every combination of layers
(air, land, water, and their unions) for a chosen **region** (Europe is the
focus; North America, Asia, Africa, Oceania and the whole world are a
`--region` flag away). Each run produces *X standard networks* and *X
evaluations* that are directly comparable. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick start (planned)

Everything runs in Docker — no manual installs.

```bash
# build the image once
docker compose build

# MODULE 1 + 2: retrieve data and generate the European air network
docker compose run --rm app retrieve openflights        # → data/raw/air/
docker compose run --rm app netgen build \
    --region europe --layers air                        # → data/processed/europe/air.graphml

# MODULE 3 + viz: run one experiment and emit interactive HTML
docker compose run --rm app evaluate run --config configs/sir_betweenness.yaml
docker compose run --rm app viz build --run <run_id>    # → figures/.../ *.html

# full sweep (regions × layer combos × models × strategies × seeds)
nextflow run workflow/main.nf -with-docker
```

For local development without Docker: `uv sync` then `uv run <cmd>`
(equivalently `uv run pytest`). See [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md).

## Building the paper

```bash
cd docs/tex
tectonic main.tex        # or: latexmk -pdf main.tex
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [`docs/README.md`](docs/README.md) | **Documentation index** — start here |
| [`docs/literature-review.md`](docs/literature-review.md) | Annotated references, old → recent |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Three-module pipeline, data flow, Nextflow rationale |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How models are used and **how parameters are justified** |
| [`docs/DATA.md`](docs/DATA.md) | Data sources, provenance, multimodal layers |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Implementation status and planned work |
| [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md) | Reproducibility, conventions, how to extend |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow for collaborators |

## License

See [`LICENSE`](LICENSE). _Add one before sharing externally._

# netsci-disease-spread

Simulating infection models and topology-aware vaccination strategies on
the European air-travel network.

> **Status:** early research project (MSc Network Science coursework).
> The repository currently contains the project blueprint, the paper draft,
> and design documentation. The simulation code described below is the
> intended layout and is being implemented — see [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What this is

We model how an epidemic spreads along European aviation routes and test
which vaccination strategy contains it best. The substrate is the European
subgraph of the [OpenFlights](https://openflights.org/data.html) route
network (airports = nodes, routes = weighted edges). On it we run four
compartmental dynamics — **SIR, SIS, SEIR, SQIR** — and compare
vaccination by **random**, **degree**, and **betweenness** targeting, plus
a **subgraph/core-aware** targeting layer that is our novel contribution.

The accompanying paper is in [`docs/tex/`](docs/tex/) (KDD Explorations
double-column format). Background and the annotated reading list are in
[`docs/literature-review.md`](docs/literature-review.md).

## Research questions

1. How does vaccination affect the infected network across different
   infection models and disease parameters?
2. Does the best strategy depend on network topology, and how important is
   vaccination on a realistic mobility substrate?
3. **(Novelty)** Can local structure — `k`-cores, motifs, graphlet
   signatures — improve *targeting* and *explain* model–strategy outcomes
   better than node-level centrality alone?

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

```bash
# environment
python -m venv .venv && source .venv/bin/activate
pip install -e .

# MODULE 1 + 2: retrieve data and generate the European air network
python -m src.retrieve.openflights                 # → data/raw/air/
python -m src.netgen.build --region europe --layers air \
    --out data/processed/europe/air.graphml

# MODULE 3: run one experiment
python -m src.evaluate.run --config configs/sir_betweenness.yaml

# run the full sweep (regions × layer combos × models × strategies)
nextflow run workflow/main.nf -profile local
```

## Building the paper

```bash
cd docs/tex
tectonic main.tex        # or: latexmk -pdf main.tex
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [`docs/literature-review.md`](docs/literature-review.md) | Annotated references, old → recent |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Three-module pipeline, data flow, Nextflow rationale |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How models are used and **how parameters are justified** |
| [`docs/DATA.md`](docs/DATA.md) | Data sources, provenance, multimodal layers |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Implementation status and planned work |
| [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md) | Reproducibility, conventions, how to extend |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow for collaborators |

## License

See [`LICENSE`](LICENSE). _Add one before sharing externally._

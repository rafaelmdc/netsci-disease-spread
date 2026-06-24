# netsci-disease-spread

Simulating infection models and topology-aware vaccination strategies on
transport networks — starting with European air travel and extending to
multimodal (air / land / water) substrates and every world region.

> **Status:** MSc Network Science coursework project. The full pipeline is
> **implemented and tested** — data retrieval, multimodal network generation,
> the metapopulation epidemic engine, vaccination strategies, the
> air-interdiction experiment, and an interactive one-tab results explorer.
> See [`docs/ROADMAP.md`](docs/ROADMAP.md) for what's done vs. open.

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
subgraph refinement). We also run an **air-interdiction** experiment — close
flight routes and watch whether land and ferry travel still carry the outbreak
— the result only the multilayer model can produce. Results are delivered as
interactive, browser-based HTML and a one-tab **Dash explorer** that builds its
own tables on launch (`netsci viz app`).

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

## Repository layout

```
.
├── experiment.yaml        # MASTER CONFIG — the 8 networks + the whole sweep grid
├── data/                  # raw + processed network data (git-ignored; see docs/DATA.md)
│   ├── raw/               # OpenFlights / GeoNames / OSM dumps, unmodified
│   └── processed/         # <region>/<combo>.graphml (the built networks)
├── src/
│   ├── retrieve/          # MODULE 1: pull raw data per layer (openflights, geonames, ferries)
│   ├── netgen/            # MODULE 2: standardise layers → emit each network as GraphML
│   ├── evaluate/          # MODULE 3: epidemic engine + strategies + metrics + interdiction
│   │   ├── models/        #   SIR / SIS / SEIR / SQIR (metapopulation R-D)
│   │   ├── strategies/    #   vaccination targeting (control/random/degree/betweenness/subgraph)
│   │   ├── metrics/       #   ρ(degree, betweenness) + FDR anomalous-gateway detection
│   │   ├── interdiction.py#   close-the-airports experiment (scenarios A–D)
│   │   └── aggregate.py   #   collect runs → summary / strategy-gap / structure tables
│   └── viz/               # curves, animated geo map, structure, panels, site + Dash app
├── results/               # simulation outputs + co-located figures (git-ignored)
├── docs/                  # paper, literature review, design docs
└── tests/                 # pytest (70 tests)
```

The pipeline is **three modules** — *data retrieval → network generation →
evaluation* — where network generation builds each chosen **(region × layer-set)**
network for a chosen **region** (Europe is the focus; Americas, Asia, Africa,
Oceania and the whole world are listed in `experiment.yaml`). See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the experiment design in
[`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## Quick start

```bash
# install (project venv). The `app` extra adds the Dash explorer.
uv sync --extra app                       # or: pip install -e ".[app]"

# MODULE 1 + 2: retrieve data and build every network in experiment.yaml
netsci retrieve openflights               # → data/raw/air/   (also: geonames, ferries)
netsci netgen build-all                   # → data/processed/<region>/<combo>.graphml

# MODULE 3: run the whole sweep, then aggregate
netsci evaluate sweep                     # runs the grid from experiment.yaml
netsci evaluate collect                   # → results/summary.parquet + strategy_gap.parquet

# the air-interdiction experiment (flagship multilayer network)
netsci evaluate interdiction --config <run.yaml>

# explore EVERYTHING in one browser tab (builds its tables on launch)
netsci viz app                            # → http://127.0.0.1:8050
# or a navigable static site of co-located HTML:
netsci viz site                           # → results/index.html
```

Run the tests with `uv run pytest`. A `Dockerfile`/`nextflow.config` exist as
optional scaffolding, but the local `netsci` CLI above is the supported path.
See [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md).

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
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Three-module pipeline, data flow, output layout, viz stack |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How models are used and **how parameters are justified** |
| [`docs/DATA.md`](docs/DATA.md) | Data sources, provenance, multimodal layers |
| [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) | The 8 networks, per-network run plan, interdiction A–D |
| [`docs/VISUALIZATION.md`](docs/VISUALIZATION.md) | Navigable outputs, animated map, Dash explorer |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Implementation status and planned work |
| [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md) | Reproducibility, conventions, how to extend |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow for collaborators |

## License

See [`LICENSE`](LICENSE). _Add one before sharing externally._

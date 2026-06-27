# netsci-disease-spread

Simulating infection models and topology-aware vaccination strategies on
transport networks — starting with European air travel and extending to
multimodal (air / land / water) substrates and every world region.

> **Status:** MSc Network Science coursework project. The full pipeline is
> **implemented and tested** — data retrieval, multimodal network generation,
> the metapopulation epidemic engine, vaccination strategies, the
> air-interdiction experiment, and an interactive simulator web app.
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
interactive, browser-based HTML and a **simulator web app** (`netsci dashboard`)
where you design a run, watch it stream live day-by-day, and explore the result.

The accompanying paper is in [`docs/tex/`](docs/tex/) (KDD Explorations
double-column format). Background and the annotated reading list are in
[`docs/literature-review.md`](docs/literature-review.md), with a full
documentation index at [`docs/README.md`](docs/README.md).

## Research questions

1. How does vaccination affect the infected network across different
   infection models and disease parameters?
2. Where does Europe sit on the degree–betweenness
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
│   ├── viz/               # curves, animated geo map, structure, panels, static site (Plotly builders)
│   └── dashboard/         # the simulator web app: FastAPI + arq worker (reuses viz's figures)
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

**The simulator app needs only [Docker](https://docs.docker.com/get-docker/)**
(plus `make`, which ships with every Linux distro) — no Python, no Nextflow.
From a fresh clone:

```bash
make app-build        # build the image once
make app              # launch the simulator → open http://127.0.0.1:8000 when it finishes
```

After the one-time build, `make app` starts in seconds; the source is
bind-mounted, so code edits are picked up without a rebuild. On a fresh clone the
app starts empty — open the **Data** tab to retrieve the sources (air + cities
download once; ferries are vendored) and build a network, then run a scenario.
Everything else (the batch Nextflow pipeline below) is optional.

The **simulator** is the interactive front end: design a scenario
(region, layers, disease model, vaccination strategy), launch it, and watch the
epidemic curve build **live, day by day**; when a run ends early, add more days
to continue from where it stopped. It reuses the same engine and figures as the
batch pipeline, so results land in the usual `results/` tree (with Gephi export).

### Optional: the full batch pipeline (needs Nextflow)

If you also want the one-shot reproducible study (every region × layer-set,
full sweep, interdiction, static site), that path additionally needs
[Nextflow](https://www.nextflow.io/) on the host: (but an equivalent one can be ran
via the dashboard app)

```bash
make run        # build the image, then run the whole pipeline via Nextflow
```

`make run` chains all three modules — **retrieve → netgen → evaluate** — through
Nextflow's live progress UI: retrieve data → build every `(region × layer-set)`
network → run the full sweep with per-node outbreak maps → collect → structure →
{ interdiction, navigable site }. Outputs land on the host under `data/` and
`results/` (the site is `results/index.html`). The water/ferry layer ships as a
**vendored snapshot** (`vendor/ferries_world.json`), so the run never depends on
a live OpenStreetMap query.

Customise via Nextflow params:

```bash
make run NFARGS="--maps false"                              # skip the heavy (~2 GB) outbreak maps
make run NFARGS="--config configs/experiment_multimodal.yaml"
make run NFARGS="--interdiction configs/europe_interdiction.yaml"
```

<details>
<summary>Without Docker (run <code>netsci</code> directly in your env)</summary>

```bash
uv sync --extra dashboard                 # or: pip install -e ".[dashboard]"
make bake                                 # same pipeline, local executor, no container
# or step by step:
netsci retrieve all                       # → data/raw/{air,geonames,water}/   (ferries from vendored snapshot)
netsci netgen build-all                   # → data/processed/<region>/<combo>.graphml
netsci evaluate sweep --maps              # runs the grid from experiment.yaml
netsci evaluate collect                   # → results/summary.parquet + strategy_gap.parquet
netsci evaluate interdiction --config configs/europe_interdiction.yaml
netsci viz site                           # → results/index.html (static HTML)

# the simulator app needs Redis + a worker (separate processes):
docker run -d -p 6379:6379 redis:7-alpine
netsci worker &                           # the arq job runner
netsci dashboard                          # → http://127.0.0.1:8000
```

To rebuild the ferry snapshot from a live Overpass sweep:
`netsci retrieve ferries --force`.

</details>

Run the tests with `uv run pytest`. See [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md).

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
| [`docs/VISUALIZATION.md`](docs/VISUALIZATION.md) | Navigable outputs, animated map, the simulator web app |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Implementation status and planned work |
| [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md) | Reproducibility, conventions, how to extend |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow for collaborators |

## License

See [`LICENSE`](LICENSE). _Add one before sharing externally._

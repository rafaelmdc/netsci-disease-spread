# netsci-disease-spread

Simulating disease spread and topology-aware vaccination on the European
transport network, modelled as a shared-node multilayer graph of **air**,
**land**, and **water** mobility. An MSc Network Science project.

## Authors & contributions

An MSc Bioinformatics group project.

- **Matilde Maria** — literature review, methodology, data analysis, and writing.
- **Lucas Caridade** — literature review, results interpretation, and writing.
- **Rafael Correia** — software and the simulator app, and data analysis.

> **AI assistance.** Claude (Anthropic), via Claude Code, was used as a coding
> and writing assistant — for parts of the implementation, refactoring,
> documentation, and figure code. All design decisions, results, and final text
> were reviewed and validated by the authors.

## What this is

We ask how an epidemic spreads across a transport network and which
network-science protection contains it best. Cities are nodes; travel routes
are weighted edges drawn from open data ([OpenFlights](https://openflights.org/data.html)
air routes, GeoNames populations, OpenStreetMap/GRIP road and rail, and
OpenStreetMap ferries). The **air**, **land**, and **water** layers share one
node set, and the **region** is a construction parameter, so the same analysis
runs for Europe (the focus) and for other world regions.

On each network we run **five disease types** as a metapopulation
reaction–diffusion process:

| Type | Model | Exemplar |
|------|-------|----------|
| Immunizing, acute | SIR | measles |
| Latent + immunizing | SEIR | COVID |
| Lethal, isolation-controlled | SEIQRD | Ebola |
| Endemic, no immunity | SIS | gonorrhea |
| Recurrent, waning immunity | SEIRS | influenza |

Every parameter is fixed from the literature, not tuned. We then compare
vaccination that protects cities chosen by **random**, **degree**,
**betweenness**, **subgraph centrality**, **Collective Influence**, and
**non-backtracking** targeting against an unprotected control, and run an
**air-interdiction** experiment (close flight routes and watch whether land and
ferry travel still carry the outbreak) — a result only the multilayer model can
produce.

## Research questions

1. How do the five disease types respond to each vaccination strategy, and how
   much protection does the best strategy buy as the vaccination budget grows
   (the dose–response)?
2. Where does Europe sit on the degree–betweenness spectrum? Where the two
   centralities correlate, degree- and betweenness-targeted immunisation
   coincide; where low-degree/high-betweenness gateways appear, they diverge.
   The region parameter answers this by direct cross-region comparison.
3. Can closing air routes contain an outbreak, or do the land and ferry layers
   still carry it across the region?

## Key results

- **Betweenness targeting wins across all five disease types**, and the gap over
  degree targeting is largest exactly where anomalous low-degree gateways exist.
- Europe sits between the US-like regime (degree ≈ betweenness) and the
  worldwide regime (many anomalous gateways), so strategy choice matters.
- **Closing all air routes does not contain the epidemic on the multilayer
  substrate**: land and ferry travel still leave 32–47% of the peak standing, whereas an
  air-only model would call the outbreak contained — the clearest argument in
  the study for building the multilayer network rather than the air network
  alone.

The full write-up is the paper in [`docs/curated_tex/`](docs/curated_tex/)
(`main.pdf`).

## Repository layout

```
.
├── experiment.yaml        # master config: the 8 networks + the full sweep grid
├── data/                  # raw + processed network data (git-ignored; see docs/DATA.md)
│   ├── raw/               # OpenFlights / GeoNames / OSM dumps, unmodified
│   └── processed/         # <region>/<combo>.graphml (the built networks)
├── src/
│   ├── retrieve/          # module 1: pull raw data per layer
│   ├── netgen/            # module 2: standardise layers → emit each network as GraphML
│   ├── evaluate/          # module 3: epidemic engine + strategies + metrics + interdiction
│   │   ├── models/        #   SIR / SIS / SEIR / SEIRS / SEIQRD (metapopulation R-D)
│   │   ├── strategies/    #   vaccination targeting
│   │   ├── metrics/       #   degree–betweenness + FDR anomalous-gateway detection
│   │   ├── interdiction.py#   close-the-airports experiment (scenarios A–D)
│   │   └── aggregate.py   #   collect runs → summary / structure / deaths / equity tables
│   ├── viz/               # curves, geo map, structure figures, static site (Plotly)
│   └── dashboard/         # interactive simulator web app (FastAPI + arq worker)
├── results/               # simulation outputs + figures (git-ignored)
├── docs/                  # the paper, literature review, and design docs
└── tests/                 # pytest
```

The pipeline is **three modules** — *data retrieval → network generation →
evaluation* — where network generation builds each chosen **(region × layer-set)**
network. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the experiment
design in [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## Running it

The interactive **simulator app** needs only
[Docker](https://docs.docker.com/get-docker/) (plus `make`). From a fresh clone:

```bash
make app-build        # build the image once
make app              # launch → open http://127.0.0.1:8000
```

The app is the interactive front end: design a scenario (region, layers, disease
type, vaccination strategy), launch it, and watch the epidemic curve build
**live, day by day**. On a fresh clone the app starts empty — open the **Data**
tab to retrieve the sources and build a network, then run a scenario. It reuses
the same engine and figures as the batch pipeline, so results land in the usual
`results/` tree.

To reproduce the full study in one command (every region × layer-set, the full
sweep, interdiction, and the static site), the batch pipeline additionally needs
[Nextflow](https://www.nextflow.io/) on the host:

```bash
make run              # retrieve → build every network → sweep → collect → interdiction → site
```

Run the tests with `uv run pytest`.

## Documentation

| Doc | Purpose |
|-----|---------|
| [`docs/literature-review.md`](docs/literature-review.md) | Annotated references and how this work is positioned |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | How the models are used and how parameters are justified |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | The three-module pipeline, data flow, and visualization stack |
| [`docs/DATA.md`](docs/DATA.md) | Data sources, provenance, and the multimodal layers |
| [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) | The networks, the run plan, and the interdiction scenarios |
| [`docs/VISUALIZATION.md`](docs/VISUALIZATION.md) | Navigable outputs, the animated map, and the simulator app |

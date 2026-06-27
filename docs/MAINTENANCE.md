# Maintenance & Reproducibility

Conventions that keep the project reproducible and easy to extend. Aimed
at future-us and any collaborator picking this up cold.

## Reproducibility contract

- **A run is a pure function of `(config, seed)`.** No hidden global state,
  no un-seeded randomness. Every stochastic call takes an explicit RNG.
- **Config is the source of truth.** `experiment.yaml` at the repo root is the
  master config — the 8 networks and the whole sweep grid (regions, layers,
  models, params, strategies, coverages, sensitivity axes, seeds). A single run
  can also be specified by a small YAML for `netsci evaluate run`. No magic
  numbers in code.
- **Raw data is rebuilt, not committed.** `data/` and `results/` are git-ignored;
  reproduce them via `src/retrieve` + the pipeline. Record source versions in
  `data/raw/<layer>/PROVENANCE.txt`. **One exception:** the vendored ferry
  snapshot `vendor/ferries_world.json` is committed so a clean-clone run is
  deterministic and offline (rationale in [`DATA.md`](DATA.md)).
- **Retrieval is idempotent.** Each `netsci retrieve` source skips an
  already-cached file; `--force` refetches. So the pipeline's first stage is a
  no-op on reruns.
- **Pin the environment.** Dependencies are pinned in `pyproject.toml`
  (+ `uv.lock`); the `dashboard` extra adds the simulator web app. The Docker image is
  built from the same lockfile (`uv sync --frozen`), so containerised and local
  runs are byte-identical.

## Running the pipeline

The supported **one command** is Nextflow inside the project Docker image —
host prerequisites are just Docker and Nextflow (Java), no local Python:

```bash
make run                               # docker compose build + nextflow run -ansi-log true
make app                               # simulator web app → http://127.0.0.1:8000
# customise via Nextflow params:
make run NFARGS="--maps false"         # skip the heavy (~2 GB) per-node outbreak maps
make run NFARGS="--config configs/experiment_multimodal.yaml"
```

`make run` chains all three modules: `retrieve → netgen build-all →
evaluate sweep [--maps] → collect → structure → {interdiction, site}`. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) § "Orchestrating the sweep" for the DAG
and how `nextflow.config` bind-mounts artifacts onto the host.

### Without Docker (development)

`uv sync --extra dashboard` reproduces the locked environment (or
`pip install -e ".[dashboard]"`); then either `make bake` (the same DAG via
`nextflow -profile local`) or the bare `netsci` CLI per stage:

```bash
netsci retrieve all                    # → data/raw/{air,geonames,water}/  (ferries from vendored snapshot)
netsci netgen build-all                # every network in experiment.yaml → data/processed/
netsci evaluate sweep --maps           # the whole grid (+ per-node history for the maps)
netsci evaluate collect                # → summary.parquet + strategy_gap.parquet
netsci evaluate structure              # → structure.parquet (degree–betweenness spectrum)
netsci evaluate interdiction --config configs/europe_interdiction.yaml  # scenarios A–D
netsci viz site                        # navigable static site of co-located HTML
```

The **simulator app** needs Redis + a worker alongside the web process:

```bash
docker run -d -p 6379:6379 redis:7-alpine   # or any Redis; set REDIS_URL to point at it
netsci worker &                              # arq job runner (executes simulations)
netsci dashboard                             # FastAPI app → http://127.0.0.1:8000
```

## run_id and human-readable labels

Every run has a `run_id` = stable hash of its **resolved** pydantic config
(model, params, strategy, coverage, seed, network, horizon, τ, …) — used for
dedup/caching. On disk a run is a **self-contained folder** named by a
human-readable **`label`**:

```
results/<region>/<combo>/<label>/
    summary.json            # config + network stats + structural + summary
    timeseries.parquet      # per-day compartment totals
    node_timeseries.parquet # per-node infectious/day (only if recorded — for the map)
    curves.html / spread_geo.html / index.html   # co-located figures (netsci viz site)
```

e.g. `results/europe/air/sir_betweenness_cov75_seed0_7c21a4/` — the label is
`<model>_<strategy>_cov<coverage>_seed<seed>_<run_id[:6]>` (the short run_id
suffix keeps otherwise-identical labels unique). `record_nodes` is *not* part of
the hashed config, so recording the per-node history doesn't fork the `run_id`.
`evaluate collect` (via `src/evaluate/aggregate.py`) walks `results/**/summary.json`
into `results/summary.parquet` plus `strategy_gap.parquet` (the degree-vs-
betweenness thesis number); `structure.parquet` is computed per built network.
Figures live **inside** the run/network folder, sharing one `plotly.min.js` at
the results root. Never derive any of this from anything outside the config.

## Conventions

- **Add a layer** → new fetcher in `src/retrieve/` + standardiser in
  `src/netgen/`. Do not touch `evaluate`.
- **Add a strategy** → one file in `src/evaluate/strategies/` with the
  signature `(graph, budget, **params) -> set[node]`.
- **Add a model** → one file in `src/evaluate/models/` subclassing
  `CompartmentalModel` with `reaction(state, params, pressure) -> state`; the
  engine owns diffusion/commuting and the inert `V` compartment, so models stay
  local-dynamics-only.
- **Add a region** → a region value in `experiment.yaml`'s `networks` list;
  no new module.
- Keep layers **tagged** by per-layer edge weights (`w_air`/`w_water`/`w_land`);
  never merge into one untagged edge set. Interdiction relies on this tagging.

## Numerical & scientific hygiene

- Report $R_0$, not just $\beta$ — and derive $\beta$ from $R_0$ with the
  network correction (see [`METHODOLOGY.md`](METHODOLOGY.md)).
- Every headline claim must survive the sensitivity sweep.
- Distinguish **comparative** claims (robust) from **absolute** incidence
  (illustrative, because the population/travel rate are synthetic).

## Paper build

```bash
cd docs/tex && tectonic main.tex        # or latexmk -pdf main.tex
```
Keep `references.bib` the single bibliography. **Never cite an entry marked
`⚠ UNVERIFIED` / `PLACEHOLDER`** until its full citation is confirmed. (The
former `tanaka:centrality` placeholder is resolved: replaced by the verified
`sun:anomalous` — Sun, Hu & Zhu 2023, EPJ Plus, doi:10.1140/epjp/s13360-023-04003-3.)

## Testing

`uv run pytest` (70 tests, ruff clean). Coverage includes:

- Each model against the well-mixed analytic limit (single node, no migration
  → classic SIR/SEIR curve) and conservation of population.
- Determinism: identical `(config, seed)` → identical outputs / `run_id`.
- Strategy selectors return the right nodes deterministically.
- Network generation: gravity catchment, authoritative served-city resolution.
- Viz layer: per-node recording, figure builders, run catalogue.
- Interdiction transforms (close layer / close airports) and scenario runner.
- FDR anomalous-gateway detection flags a planted low-degree bridge.

## Housekeeping

- `docs/ROADMAP.md` is the status board — update it when phases move.
- Convert any relative dates in notes to absolute (YYYY-MM-DD).

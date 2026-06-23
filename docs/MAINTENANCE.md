# Maintenance & Reproducibility

Conventions that keep the project reproducible and easy to extend. Aimed
at future-us and any collaborator picking this up cold.

## Reproducibility contract

- **A run is a pure function of `(config, seed)`.** No hidden global state,
  no un-seeded randomness. Every stochastic call takes an explicit RNG.
- **Configs are the source of truth.** One YAML in `configs/` fully
  specifies a run (region, layers, model, params, strategy, coverage,
  efficacy, seed). No magic numbers in code.
- **Data is never committed.** `data/` and `results/` are git-ignored;
  reproduce them via `src/retrieve` + the workflow. Record source versions
  in `data/raw/<layer>/PROVENANCE.txt`.
- **Pin the environment.** Lock dependencies (`requirements.txt` /
  `pyproject.toml` + lockfile). Record Python and key library versions.

## Docker workflow

The container is the source of truth for the environment — no manual
installs. Build once with `docker compose build`; run any module with
`docker compose run --rm app <command>` (the `app` service entrypoint is the
typer CLI). A `notebook` service exposes Jupyter for exploration. Nextflow
uses the *same* image (`docker.enabled = true`, `process.container` in
`nextflow.config`), so pipeline and interactive runs are byte-identical.
For local dev without Docker, `uv sync` reproduces the locked environment.

## run_id and human-readable labels

Every run has a `run_id` = stable hash of its **resolved** pydantic config
(model, params, strategy, coverage, seed, network, horizon, τ, …) — used for
dedup/caching. Files are named by a human-readable **`label`** instead, e.g.
`sir_betweenness_cov75_seed0_7c21a4.json` (model, strategy, coverage, seed +
a short run_id suffix for uniqueness). `results/summary.csv` (from
`evaluate collect`) is the human-facing table, led by `label` with rounded
counts. Never derive either from anything outside the config.

## Conventions

- **Add a layer** → new fetcher in `src/retrieve/` + standardiser in
  `src/netgen/`. Do not touch `evaluate`.
- **Add a strategy** → one file in `src/evaluate/strategies/` with the
  signature `(graph, budget, **params) -> set[node]`.
- **Add a model** → one file in `src/evaluate/models/` implementing
  `step(state, graph, params) -> state`. Keep reaction and diffusion
  separable.
- **Add a region** → a `--region` value handled in `netgen`; no new module.
- Keep layers **tagged** in the multilayer graph (edge attribute `layer`);
  never merge into one untagged edge set.

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
`⚠ UNVERIFIED` / `PLACEHOLDER`** (currently: `tanaka:centrality`) until its
full citation is confirmed.

## Testing (once code exists)

- Unit-test each model against the well-mixed analytic limit (single node,
  no migration → classic SIR/SEIR curve).
- Golden-file test one full small run so refactors can't silently change
  results.
- Test that strategy selectors return exactly `budget` nodes and are
  deterministic under a fixed seed.

## Housekeeping

- `docs/ROADMAP.md` is the status board — update it when phases move.
- Convert any relative dates in notes to absolute (YYYY-MM-DD).

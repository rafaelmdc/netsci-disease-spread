# Contributing

Small team / course project. Keep it light but reproducible.

## Workflow

1. Branch off `main` (`feat/...`, `docs/...`, `fix/...`). Don't commit to
   `main` directly.
2. Keep PRs small and focused. Describe *what* and *why*.
3. One reviewer before merge when feasible.

## Ground rules

- **Reproducibility first** — see [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md).
  Runs are a pure function of `(config, seed)`; data and results are
  git-ignored.
- **No magic numbers** — parameters live in `configs/`, justified in
  [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).
- **Cite real sources only.** Add references to
  [`docs/tex/references.bib`](docs/tex/references.bib) and annotate them in
  [`docs/literature-review.md`](docs/literature-review.md). Mark anything
  unverified `⚠ UNVERIFIED` and do not cite it in the paper until checked.
- **Module boundaries** — retrieve → netgen → evaluate. Respect the
  contracts in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Commit messages

Imperative mood, short subject, why-in-body. Group logical changes.

## Before opening a PR

- [ ] Paper still builds (`cd docs/tex && tectonic main.tex`) if you
      touched `tex/`.
- [ ] New parameters are in a config and cited.
- [ ] New references are verified and annotated.
- [ ] `docs/ROADMAP.md` updated if a phase moved.

# Documentation Index

Everything explaining the *what*, *why*, and *how* of this project. Code
lives in [`../src`](../src); this folder is the design + writeup.

## Start here (suggested reading order)

1. **[../README.md](../README.md)** — project overview, layout, quick start.
2. **[literature-review.md](literature-review.md)** — annotated references
   (old → recent) and the gap we fill. Read to understand *why* the project
   is positioned the way it is.
3. **[METHODOLOGY.md](METHODOLOGY.md)** — how the models are used and, above
   all, **how parameters are justified** (and why we don't hard-calibrate).
4. **[ARCHITECTURE.md](ARCHITECTURE.md)** — the three-module pipeline, data
   flow, I/O contracts, Docker, and interactive-visualization plan.
5. **[DATA.md](DATA.md)** — data sources, provenance, and the multimodal
   (air/land/water) layers with their coverage and consistency rules.
6. **[ROADMAP.md](ROADMAP.md)** — status board and the build slices.
7. **[MAINTENANCE.md](MAINTENANCE.md)** — reproducibility contract and
   conventions for extending the code.

## Reference

| Doc | What it covers |
|-----|----------------|
| [literature-review.md](literature-review.md) | ~25 verified references, grouped by theme; the novelty argument |
| [METHODOLOGY.md](METHODOLOGY.md) | Model definitions, parameter strategy, calibration vs. verification, comparison-axis consistency |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Modules, contracts, Nextflow, Docker, HTML visualizers |
| [DATA.md](DATA.md) | OpenFlights + land/water sources; topology vs. flow coverage; Eurostat-as-validation |
| [ROADMAP.md](ROADMAP.md) | Phases / vertical slices, open decisions |
| [MAINTENANCE.md](MAINTENANCE.md) | Determinism, configs, run_id, Docker workflow, testing |
| [tex/](tex/) | The paper (KDD Explorations double-column). Build: `tectonic tex/main.tex` |
| [sources/](sources/) | Original project blueprint PDF |

## The paper

The manuscript is in [`tex/main.tex`](tex/main.tex) with
[`tex/references.bib`](tex/references.bib). It compiles with **tectonic**
(or `latexmk -pdf`). The narrative there is the source of truth for the
scientific framing; the docs above are the engineering and reasoning behind
it.

## Status legend (used across docs)

- ✅ done · ⛔ not started · ⚠ needs verification (e.g. the unverified
  *Tanaka 2014* reference, still a placeholder in `tex/references.bib`).

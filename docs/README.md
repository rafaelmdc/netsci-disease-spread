# Documentation

Everything explaining the *what*, *why*, and *how* of this project. Code lives
in [`../src`](../src); this folder is the writeup and design.

## The paper

The manuscript is in [`curated_tex/`](curated_tex/) — read the built PDF at
[`curated_tex/main.pdf`](curated_tex/main.pdf). It is the source of truth for the
scientific framing; the docs below are the reasoning and engineering behind it.

## Suggested reading order

1. **[../README.md](../README.md)** — project overview, layout, how to run.
2. **[literature-review.md](literature-review.md)** — annotated references
   (old → recent) and how the project is positioned.
3. **[METHODOLOGY.md](METHODOLOGY.md)** — how the models are used and, above
   all, how parameters are justified.
4. **[ARCHITECTURE.md](ARCHITECTURE.md)** — the three-module pipeline, data
   flow, and the visualization stack.
5. **[DATA.md](DATA.md)** — data sources, provenance, and the multimodal
   (air/land/water) layers.
6. **[EXPERIMENTS.md](EXPERIMENTS.md)** — the networks built, what runs on
   each, and the air-interdiction experiment.
7. **[VISUALIZATION.md](VISUALIZATION.md)** — the navigable outputs, the
   animated outbreak map, and the simulator web app.

## Reference

| Doc | What it covers |
|-----|----------------|
| [literature-review.md](literature-review.md) | Verified references, grouped by theme; the positioning argument |
| [METHODOLOGY.md](METHODOLOGY.md) | Model definitions, parameter strategy, comparison-axis consistency |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Modules, contracts, output layout, HTML visualizers, the simulator app |
| [DATA.md](DATA.md) | OpenFlights + land/water sources; topology vs. flow coverage |
| [EXPERIMENTS.md](EXPERIMENTS.md) | The networks, per-network run plan, air-interdiction scenarios A–D |
| [VISUALIZATION.md](VISUALIZATION.md) | Navigable outputs, animated map, the simulator app |
| [curated_tex/](curated_tex/) | The paper (`main.pdf`) |
| [sources/](sources/) | Original project brief |

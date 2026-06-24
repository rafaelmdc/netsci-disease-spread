# Visualization & Output Plan

How the (currently scaffold-level) evaluate + viz pipeline becomes a set of
**navigable, self-explanatory human outputs**, with every figure stored
**inside the network/run folder that produced it** — open a folder, get its
story, no separate `figures/` tree to reconcile.

Companion to [`EXPERIMENTS.md`](EXPERIMENTS.md) (what we build & run). That doc
defines 5 paper artifacts; this doc says where each one lives and how you
click to it.

---

## 1. Guiding principle

- **Figures live with their data.** A run's animation sits next to its
  `summary.json` and `timeseries.parquet`. A network's panel sits in the
  network folder. The cross-region table sits at the root.
- **Every folder is navigable.** Each level has an `index.html` linking down
  to the level below and up to its parent — a static site you can open with a
  double-click, no server.
- **Self-explanatory.** Each figure carries a title + caption describing the
  model, network, and what to look at, so it stands alone in the report.
- **Two delivery modes, same data:** standalone HTML (offline, gradeable
  artifact) is primary; the Dash explorer (§5) is an interactive shell on top.

---

## 2. Output layout (figures co-located with results)

```
results/
├── index.html                      ← TOP: cross-region ρ table + links to each network
├── summary.parquet                 ← tidy table, every run (collect step)
│
├── europe/
│   ├── air+land+water/             ← one NETWORK folder
│   │   ├── index.html              ← network page: ladder/strategy panel + run list
│   │   ├── network.html            ← the graph itself (pyvis, Gephi-style)
│   │   ├── network.gexf            ← Gephi export
│   │   ├── structure.html          ← ρ(deg,btw) scatter + anomalous gateways
│   │   ├── strategy_panel.html     ← 4 models × strategies comparison (this net)
│   │   ├── spread_geo.html         ← ⭐ animated outbreak map (representative run)
│   │   ├── interdiction.html       ← scenarios A–D triptych (flagship only)
│   │   │
│   │   ├── sir__betweenness__cov75__seed0/      ← one RUN folder
│   │   │   ├── index.html          ← run page linking the three below
│   │   │   ├── summary.json        ← metrics (exists today)
│   │   │   ├── timeseries.parquet  ← region-summed compartments/day (exists today)
│   │   │   ├── node_timeseries.parquet  ← NEW: per-node infectious/day (+lat/lon)
│   │   │   ├── curves.html         ← S/E/I/R/V curves
│   │   │   └── spread_geo.html     ← per-run animated map (if flagged to animate)
│   │   └── sir__control__seed0/ ...
│   │
│   ├── air+land/   └── (same shape)
│   └── air/        └── (same shape)
│
├── americas/air/   └── index.html + structure.html + light SIR runs
├── asia/air/ · africa/air/ · oceania/air/ · world/air/   └── (same)
```

`src/paths.py` already gives `run_dir`, `results_dir`, `processed_graph`.
We add helpers for the co-located figures (e.g. `run_figure(region, combo,
label, "curves.html")`, `network_index(region, combo)`, `results_index()`)
and **retire the separate `FIGURES` tree** so outputs aren't split in two.

---

## 3. The navigation (three clickable levels)

1. **`results/index.html` — the whole study.**
   - Cross-region table: region · ρ(deg,btw) · # anomalous gateways (artifact 1).
   - One row per network linking to its folder.
   - Europe-ladder strip: air → +land → +water (artifact 2).

2. **`results/<region>/<combo>/index.html` — one network.**
   - The network itself (`network.html`) + Gephi export.
   - `structure.html`: degree-vs-betweenness scatter, anomalous gateways flagged.
   - `strategy_panel.html`: this network's slice of the 4×3 grid (artifact 3).
   - `spread_geo.html`: the headline animated outbreak (artifact 4).
   - For the flagship: `interdiction.html` (artifact 5).
   - A table of every run linking to each run page.

3. **`results/<region>/<combo>/<label>/index.html` — one run.**
   - `curves.html` (compartments over time) + the metrics from `summary.json`
     rendered as a caption.
   - `spread_geo.html` if this run was flagged for per-node recording.

---

## 4. What each artifact shows (recap → file)

| Artifact (EXPERIMENTS.md §5) | File | Notes |
|------------------------------|------|-------|
| 1 Cross-region structural table | `results/index.html` | ρ + gateways, 8 rows |
| 2 Europe ladder structural | `results/index.html` strip + each net `structure.html` | how bridges change air→+land→+water |
| 3 Vaccination 4×3 panel | per-net `strategy_panel.html` | down=more realism, across=disease |
| 4 ⭐ Animated geo-spread | `spread_geo.html` | per-node infection over days, play+slider |
| 5 Air-interdiction triptych | `interdiction.html` (flagship) | A vs B vs C animated side by side |

---

## 5. Tech choices

- **Standalone animated HTML (primary).** Plotly `animation_frame=day` over
  per-node infectious counts on a geo scatter → play button + day slider, one
  self-contained `.html`. Offline, gradeable, embeds in the report.
- **Shared Plotly bundle (disk).** Figures reference **one** `plotly.min.js`
  written at the results root (`src/viz/assets.py`) instead of inlining the
  ~3.5 MB library in every file — `curves.html` drops from ~4.7 MB to ~18 KB
  while staying fully offline. Animation frames are inherent data, so
  `spread_geo.html` stays a few MB; record per-node history (and thus generate
  maps) only for a chosen showcase set, not all runs.
- **Dash explorer (interactive shell) — built.** `src/viz/app.py` (Dash =
  Flask + Plotly, pure Python) reads the run catalogue under results/ via
  `src/viz/catalog.py`: dropdowns for network / model / strategy, a run picker,
  and tabs for the animated **outbreak map**, **epidemic curves**, **strategy
  comparison** and **region spectrum**. It *reads precomputed outputs*, so it's
  instant; when a run lacks per-node history the map tab offers a one-click
  re-simulation that records it. Chosen over bare Flask to avoid hand-writing
  HTML/JS for the controls.

  ```bash
  uv sync --extra app          # installs dash + dash-bootstrap-components
  netsci viz app               # serves http://127.0.0.1:8050 — browse every run
  ```

---

## 6. Evaluate changes that unlock the above

| Change | Why |
|--------|-----|
| **Persist per-node history (opt-in)** | `engine.simulate(record_nodes=True)` already returns `node_infectious`; `runner` must write `node_timeseries.parquet` (+ node lat/lon) for runs flagged to animate. *Keystone — unlocks every animation.* Opt-in so we don't store per-node × per-day for all ~500 runs. |
| **Structural metrics module** | ρ(deg,btw) **+ anomalous-gateway detection** with a defined threshold (Sun-Hu-Zhu FDR benchmark), per-node centralities → `structure.html` |
| **Strategy-contrast metrics** | benefit-over-control + degree-vs-betweenness final-size gap (the thesis number) → `strategy_panel.html` |
| **Interdiction runner** | edge-layer removal scenarios A–D → `interdiction.html` |
| **`collect` → `summary.parquet`** | one tidy table feeding every index page and the Dash app |
| **Index generators** | emit the three levels of `index.html` after a sweep |

---

## 7. Build order

1. ✅ **Keystone:** per-node history persisted (opt-in `record_nodes`), figures
   co-located in run/network folders, `FIGURES` tree retired.
2. ✅ **Animated geo-spread HTML** (`spread_html.py`, `netsci viz animate`).
3. ✅ **Dash explorer** (`app.py`, `netsci viz app`) — browse every run,
   animated map / curves / compare / spectrum tabs, on-demand map generation.
4. ✅ **Index generators** → navigable three-level static site
   (`src/viz/site.py`, `netsci viz site`): root + per-network + per-run
   `index.html`, figures co-located.
5. ✅ **Structural + strategy figures** → `structure.html` (degree-vs-betweenness
   scatter, anomalous gateways) and `strategy_panel.html` (per-network 4-model
   strategy panel).
6. ✅ **Interdiction** experiment (`src/evaluate/interdiction.py`,
   `netsci evaluate interdiction`) + curves figure → `interdiction.html`.

> Done: anomalous gateways now use a **degree-conditioned Benjamini-Hochberg
> FDR** test (`metrics.anomalous_gateways`) instead of an arbitrary quantile,
> and `collect` writes a **degree-vs-betweenness gap** table
> (`results/strategy_gap.parquet`) — the headline thesis number per
> network/model/coverage.

# Experiment & Network Plan

What we build, what we run on it, and which paper artifact each produces.
The guiding rule: **every network earns its place by answering one sentence
in the paper.** Most networks only feed a structural table (instant, no
simulation); the full 4-model vaccination grid runs only where the story
needs it (the Europe ladder).

Central question: **In Europe, once you account for air *and* land *and*
water travel (including how long each trip takes), is the cheap
degree-targeted vaccination the same as the expensive betweenness-targeted
one — and can you even stop an outbreak by grounding flights?**

---

## 1. Networks we build (8 graphs)

| # | Region | Layers | Role in the paper |
|---|--------|--------|-------------------|
| 1 | **europe** | **air + land + water** | ⭐ flagship — the realistic Europe; all headline results live here |
| 2 | europe | air + land | middle rung of the "add realism" ladder |
| 3 | europe | air | naive baseline the multilayer is compared against |
| 4 | americas | air | cross-region spectrum (US-like pole) |
| 5 | asia | air | cross-region spectrum |
| 6 | africa | air | cross-region spectrum |
| 7 | oceania | air | cross-region spectrum (anomalous pole) |
| 8 | world | air | cross-region spectrum (worldwide / Guimerà pole) |

Two storylines share node **#3 (europe/air)** as their pivot:
- **Ladder** (#1–#3): same region, more layers each step → shows the answer
  *move* as the map gets realistic.
- **Cross-region** (#3–#8): same layer everywhere, fair comparison → where
  Europe sits among continents.

---

## 2. What runs on each network

| # | Network | ① Structure (ρ, gateways) | ② Vaccination grid | ③ Air-interdiction |
|---|---------|:---:|:---:|:---:|
| 1 | europe air+land+water | ✅ | ✅ full (108) | ✅ scenarios A–D |
| 2 | europe air+land       | ✅ | ✅ full (108) | — |
| 3 | europe air            | ✅ | ✅ full (108) | — |
| 4 | americas air          | ✅ | ◽ light (SIR, 27) | — |
| 5 | asia air              | ✅ | ◽ light (SIR, 27) | — |
| 6 | africa air            | ✅ | ◽ light (SIR, 27) | — |
| 7 | oceania air           | ✅ | ◽ light (SIR, 27) | — |
| 8 | world air             | ✅ | ◽ light (SIR, 27) | — |

- **① Structure** — `ρ(degree, betweenness)` + anomalous-gateway list.
  No simulation; seconds per graph. Runs on all 8.
- **② Vaccination grid (full)** — 4 models × (control + 4 strategies × 2
  coverages) × 3 seeds = **108 runs**. Identical grid on all three Europe
  rungs so the ladder is a true apples-to-apples comparison (only the
  layers differ). Light version = SIR only (**27 runs**) on the cross-region
  air nets, just to show the structural result has an epidemic consequence.
- **③ Air-interdiction** — flagship only. Close air routes, see if land +
  water still carry the outbreak (see §4).

---

## 3. The vaccination grid (one cell of the panel)

Each "full" cell above expands to:

| Axis | Values | Count |
|------|--------|------:|
| Disease model | SIR, SIS, SEIR, SQIR | 4 |
| Strategy | control, random, degree, betweenness, subgraph | 5 |
| Coverage | 1 % (low), 75 % (high) | 2 (control uses 1) |
| Seeds | 0, 1, 2 (averaged) | 3 |

→ 4 × (1 + 4×2) × 3 = **108 runs** per network. Fixed: 15 cities immunised,
85 % efficacy, 210-day horizon, seed 2500.

---

## 4. The air-interdiction experiment (flagship only)

Removing **edges** (close routes), not **nodes** (vaccinate cities) — the
intervention only the multilayer can express.

| Scenario | What we do | What it shows |
|----------|-----------|---------------|
| **A** | full air+land+water, no intervention | reference outbreak |
| **B** | close **all** air routes, keep land + water | do roads + ferries carry it anyway? |
| **C** | close all air in an **air-only** model | what a naive (air-only) modeller wrongly concludes |
| **D** | close only the top-_k_ airports by **degree** vs by **betweenness** | which closures matter — busy hubs or bridges? |

Run across SIR + SEIR × 3 seeds (~30–40 fast runs). **B vs C is the
headline:** air-only modelling says "ground the flights and you're safe";
the multilayer shows land/ferry travel keeps it going. **D** asks the
central question through closure instead of vaccination.

---

## 5. What the paper actually shows (the artifacts)

1. **Cross-region structural table** — 8 rows (one per network), columns
   `ρ(deg,btw)` and # anomalous gateways. Places Europe on the
   US-like ↔ worldwide-like spectrum. *(from ① on all 8)*

2. **Europe ladder structural panel** — 3 rows (air → air+land →
   air+land+water) showing how the set of critical bridge cities changes as
   layers are added. *(from ① on #1–#3)*

3. **The vaccination panel — the "4×n" you asked about** — it is
   **4 models × 3 Europe rungs = 12 cells**, each cell a
   strategy-comparison plot (final size / peak by strategy, low vs high
   coverage). Read **down a column** = same model, more realism; read
   **across a row** = same map, different disease. This is the deliverable
   grid, and it is 12 cells, *not* 32 — the cross-region nets don't enter
   here. *(from ② full on #1–#3)*

4. **Cross-region consequence strip** — small SIR-only bar per region
   (#4–#8) confirming the structural ρ has a real epidemic effect.
   *(from ② light)*

5. **Air-interdiction figure** — scenarios A–D on the flagship; the
   "grounding flights isn't enough" result. *(from ③)*

---

## 6. Run-count budget (all fast)

| Block | Runs |
|-------|-----:|
| Structure (8 graphs) | ~0 (seconds) |
| Europe ladder vaccination (3 × 108) | 324 |
| Cross-region light (5 × 27) | 135 |
| Air-interdiction | ~40 |
| **Total** | **≈ 500** |

Eight networks, ~500 fast simulations, every run mapped to a figure. Well
under the "don't brute-force" line.

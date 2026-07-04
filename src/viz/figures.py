"""Static, paper-ready result figures (matplotlib -> vector PDF/SVG).

Distinct from the ``*_html`` generators, which build the interactive Plotly
explorer. These read the collected tables in ``results/`` and write column-width
vector figures into ``docs/curated_tex/figures/`` for the article. Each figure
also drops a small CSV of the exact numbers it plots, so it is reproducible.

The curated set (one per question, no duplicates):

  F-spread       how the outbreak changes with realism, per disease type.
                 PEAK AS A FRACTION of population, not absolute, so the water
                 rung is not misread as protective (it adds peripheral coastal
                 cities that desync the peak; the denominator effect).
  F-defense      node targeting: % peak reduction vs control by strategy, both
                 diseases at the flagship -> betweenness (bridges) beats degree
                 (hubs), and it holds for both disease types.
  F-interdiction edge targeting: grouped bars of the peak remaining after each
                 closure, air-only vs multimodal -> grounding flights stops it
                 only when air is the sole carrier.
  F-dose         dose-response: peak reduction vs number of cities vaccinated,
                 both diseases' winning strategy on the flagship.
  F-curves       the epidemic curve I(t) across the realism ladder (seed-median
                 + IQR band) — peak height AND timing/desync in one figure.
  F-geo          the Europe network on real geography, betweenness-coloured, with
                 the anomalous gateways ringed; air-only vs multimodal.
  F-scatter      degree vs betweenness per city (flagship), gateways ringed —
                 the visual proof of why degree ~= betweenness as a target.
  F-degdist      degree distribution (CCDF, log-log) across the realism ladder.

Appendix (A-*): the per-seed distributions behind the headline means
  A-peak-dist    per-seed peak (% of pop) box+strip, every disease x rung.
  A-gap-dist     per-seed degree-vs-betweenness gap at the flagship.

Backing data: results/summary.parquet, the per-run timeseries.parquet, and the
per-disease two-substrate interdiction_<model>.parquet files.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.evaluate.aggregate import ci95
from src.paths import RESULTS, ROOT

# Error bars everywhere show the 95% CI of the mean across the seed ensemble
# (see docs/RESEARCH-ROADMAP.md #1). With a single-seed run the CI is 0 and the
# bars simply vanish, so the figures render either way.
ERRKW = {"ecolor": "#444444", "elinewidth": 0.7, "capsize": 2.0}

TEX = ROOT / "docs" / "curated_tex" / "figures"
COL_W = 3.4  # one column of a double-column page (inches)
WIDE = 7.0  # full text width

REGION = "europe"
FLAGSHIP = "air+land+water"
# Shared palette matched to the draw.io methodology figures (F1--F3) so the
# result figures read as the same paper: air=blue, water=orange, land=green
# (Figure~2's layer colours), with the same red/purple accents from the protocol
# boxes. These are draw.io's exact default styles: a pastel FILL plus a darker
# stroke. Bars use the pastel fill with the matching stroke as their border, just
# like the shapes in the diagrams.
FILL = {
    "blue": "#dae8fc", "orange": "#ffe6cc", "green": "#d5e8d4",
    "purple": "#e1d5e7", "red": "#f8cecc", "yellow": "#fff2cc", "gray": "#f5f5f5",
}
EDGE = {
    "blue": "#6c8ebf", "orange": "#d79b00", "green": "#82b366",
    "purple": "#9673a6", "red": "#b85450", "yellow": "#d6b656", "gray": "#666666",
}
BAR_LW = 0.8   # border weight so the pastel fills read as distinct shapes
BAR_GAP = 0.84  # drawn width as a fraction of the slot, so borders never touch


def _bar_kw(hue: str) -> dict:
    """Pastel fill + matching darker border, as in the draw.io figures."""
    return {"color": FILL[hue], "edgecolor": EDGE[hue], "linewidth": BAR_LW}


# realism ladder, in order (water added before land). Coloured by LAYER to match
# the methodology's multilayer-stack figure (air blue, water orange, land green).
RUNGS = ["air", "air+water", "air+land+water"]
RUNG_LABEL = {"air": "air", "air+water": "+water", "air+land+water": "+land"}
RUNG_HUE = {"air": "blue", "air+water": "orange", "air+land+water": "green"}
# disease types in canonical (archetype-table) order; figures plot whichever are
# present in the data, so a 2-disease or a 5-disease run both render correctly.
MODELS = ["sir", "sis", "seir", "seirs", "seiqrd"]
DISEASE = {"sir": "Measles", "sis": "Gonorrhea", "seir": "COVID",
           "seirs": "Flu", "seiqrd": "Ebola"}
DISEASE_HUE = {"sir": "red", "sis": "blue", "seir": "green",
               "seirs": "orange", "seiqrd": "purple"}
STRAT_ORDER = ["random", "degree", "betweenness", "subgraph",
               "collective_influence", "nonbacktracking"]
# compact x-axis labels (the two modern arms have long names)
STRAT_LABEL = {"collective_influence": "CI", "nonbacktracking": "non-backtrack"}


def _strat_label(s: str) -> str:
    return STRAT_LABEL.get(s, s)


def _disease(model: str, two_line: bool = False) -> str:
    name = DISEASE.get(model, model.upper())
    sep = "\n" if two_line else " "
    return f"{name}{sep}({model.upper()})"


def _style() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.size": 8, "axes.titlesize": 9,
        "axes.labelsize": 8, "legend.fontsize": 7, "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False,
        "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def _save(fig, name: str, data: pd.DataFrame | None = None) -> Path:
    TEX.mkdir(parents=True, exist_ok=True)
    pdf = TEX / f"{name}.pdf"
    fig.savefig(pdf)
    fig.savefig(TEX / f"{name}.svg")
    plt.close(fig)
    if data is not None:
        data.to_csv(TEX / f"{name}.csv", index=False)
    return pdf


# --------------------------------------------------------------------------- #
# F-spread — how the peak grows with realism, per disease type.
# We plot peak active infection AS A FRACTION of the population, not the absolute
# count. The realism ladder changes the population (the land layer adds inland,
# non-airport cities: ~199M on air -> ~342M on air+land+water), so the absolute
# peak roughly doubles largely because there are more people to infect.
# Normalising by population removes that confound and shows the real story: the
# peak fraction is nearly flat across the ladder, i.e. realism adds people, not
# per-capita severity. Ferries desynchronise the peak slightly (a small real dip).
# --------------------------------------------------------------------------- #
def _draw_spread(ax, summary: pd.DataFrame) -> pd.DataFrame | None:
    df = summary[(summary["region"] == REGION) & (summary["strategy"] == "control")]
    df = df[df["combo"].isin(RUNGS)].copy()
    if df.empty:
        return None
    df["peak_pct"] = df["peak_infected"] / df["total_population"] * 100.0
    grp = df.groupby(["model", "combo"])
    g = grp[["peak_infected", "total_population", "peak_pct"]].mean().reset_index()
    g = g.merge(
        grp["peak_pct"].agg(ci95).reset_index(name="peak_pct_ci"),
        on=["model", "combo"],
    )
    models = [m for m in MODELS if m in g["model"].unique()]
    step, x = 0.27, range(len(models))
    for i, rung in enumerate(RUNGS):
        sub = [g[(g["model"] == m) & (g["combo"] == rung)] for m in models]
        vals = [c["peak_pct"].sum() for c in sub]
        errs = [c["peak_pct_ci"].sum() for c in sub]
        ax.bar([xi + (i - 1) * step for xi in x], vals, step * BAR_GAP,
               yerr=errs, error_kw=ERRKW,
               label=RUNG_LABEL[rung], **_bar_kw(RUNG_HUE[rung]))
    ax.set_xticks(list(x))
    ax.set_xticklabels([_disease(m, two_line=True) for m in models])
    ax.tick_params(axis="x", labelsize=6.5)
    ax.set_ylabel("peak active infections\n(% of population)")
    ax.set_title("Peak active infections by disease type and substrate")
    ax.legend(title="substrate", frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.2))
    return g


def fig_spread(summary: pd.DataFrame) -> Path | None:
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.5))
    g = _draw_spread(ax, summary)
    if g is None:
        plt.close(fig)
        return None
    return _save(fig, "F-spread", g)


# --------------------------------------------------------------------------- #
# F-defense — node targeting: % peak reduction vs control, both diseases.
# --------------------------------------------------------------------------- #
def fig_defense(summary: pd.DataFrame, budget: int = 15) -> Path | None:
    s = summary[(summary["region"] == REGION) & (summary["combo"] == FLAGSHIP)]
    if s.empty:
        return None
    hi = s[s["strategy"] != "control"]["coverage"].max()
    rows = []
    for m in MODELS:
        sm = s[s["model"] == m]
        # per-seed control baseline (degree/betweenness/... share each seed's
        # initial placement, so reduction is a paired, per-seed quantity).
        ctrl = sm[sm["strategy"] == "control"].groupby("seed")["peak_infected"].mean()
        ctrl = ctrl[ctrl > 0]
        if ctrl.empty:
            continue
        for strat in STRAT_ORDER:
            cell = sm[(sm["strategy"] == strat) & (sm["coverage"] == hi)
                      & (sm["budget"] == budget)].groupby("seed")["peak_infected"].mean()
            paired = pd.concat([cell.rename("peak"), ctrl.rename("ctrl")],
                               axis=1, join="inner").dropna()
            if paired.empty:
                continue
            red_s = (paired["ctrl"] - paired["peak"]) / paired["ctrl"] * 100.0
            rows.append({"model": m, "strategy": strat,
                         "reduction_pct": red_s.mean(), "reduction_ci": ci95(red_s)})
    if not rows:
        return None
    red = pd.DataFrame(rows)
    models = [m for m in MODELS if m in red["model"].unique()]
    # only strategies actually present (so the figure renders before the two
    # modern arms are added to the sweep, and includes them once they are).
    strats = [s for s in STRAT_ORDER if s in set(red["strategy"])]
    _style()
    # Full text width: five diseases per strategy need room, so this is a wide
    # (double-column) figure. Bar width is sized to n diseases so a strategy's
    # group spans <1.0 and never collides with the neighbouring strategy.
    fig, ax = plt.subplots(figsize=(WIDE, 2.7))
    n = len(models)
    step = min(0.16, 0.82 / n)
    x = range(len(strats))
    for j, m in enumerate(models):
        off = (j - (n - 1) / 2) * step  # centre the group on each tick
        cells = [red[(red["model"] == m) & (red["strategy"] == s)] for s in strats]
        vals = [c["reduction_pct"].sum() for c in cells]
        errs = [c["reduction_ci"].sum() for c in cells]
        ax.bar([xi + off for xi in x], vals, step * BAR_GAP,
               yerr=errs, error_kw=ERRKW,
               label=_disease(m), **_bar_kw(DISEASE_HUE[m]))
    ax.set_xticks(list(x))
    ax.set_xticklabels([_strat_label(s) for s in strats])
    ax.set_ylabel("peak reduction vs no vaccination (%)")
    ax.set_ymargin(0.10)
    cov = f"{hi:.0%}" if pd.notna(hi) else ""
    ax.set_title(f"Peak reduction by vaccination strategy ({budget} cities, {cov} coverage)")
    ax.legend(frameon=False, ncol=n, loc="upper center",
              bbox_to_anchor=(0.5, -0.12), columnspacing=1.2, handletextpad=0.4)
    return _save(fig, "F-defense", red)


# --------------------------------------------------------------------------- #
# F-interdiction — edge targeting: peak remaining after each closure, air-only
# vs multimodal. One panel per CLOSURE scenario, the five diseases along x
# (grouped air-only vs multimodal). We drop the always-100% "full network"
# column; a dashed reference line marks it. This reads cleanly at five diseases
# where a per-disease panel layout collides.
# --------------------------------------------------------------------------- #
_FULL_SCN = "A · full network"
# closure scenario (raw name) -> panel title
_SCN = {
    "B · air closed, land+water open": "Close all air routes",
    "D2 · top-10 airports by betweenness closed": "Close top-10 hub airports",
}
# air-only in the air (blue) colour, multimodal in the land (green) colour: the
# added ground/ferry layers are exactly what the green stands for in Figure~2.
_SUBSTRATE = {"air": ("air-only model", "blue"),
              "air+land+water": ("multimodal", "green")}


def fig_interdiction(region: str = REGION) -> Path | None:
    series = {}
    for m in MODELS:
        p = RESULTS / region / FLAGSHIP / f"interdiction_{m}.parquet"
        if p.exists():
            series[m] = pd.read_parquet(p)
    if not series:
        return None
    models = [m for m in MODELS if m in series]
    sub_order = ["air", FLAGSHIP]
    scn_order = list(_SCN)
    out_rows = []
    for m in models:
        df = series[m]
        if "seed" not in df.columns:  # backward-compat with single-seed parquets
            df = df.assign(seed=0)
        # peak per (combo, scenario, seed); each scenario as % of that substrate's
        # own full-network peak, computed PER SEED then averaged with a 95% CI.
        pk = df.groupby(["combo", "scenario", "seed"])["infectious"].max()
        seeds = sorted(df["seed"].unique())
        for combo in sub_order:
            for scn in [_FULL_SCN, *scn_order]:
                pcts = []
                for sd in seeds:
                    full = pk.get((combo, _FULL_SCN, sd), float("nan"))
                    val = pk.get((combo, scn, sd), float("nan"))
                    if full and full > 0 and val == val:
                        pcts.append(val / full * 100.0)
                out_rows.append({
                    "model": m, "combo": combo, "scenario": scn,
                    "pct_of_full": float(np.mean(pcts)) if pcts else float("nan"),
                    "pct_of_full_ci": ci95(pcts), "n_seeds": len(pcts),
                })
    out = pd.DataFrame(out_rows)

    _style()
    # panels stacked vertically at column width: keeps this a single-column float
    # (not a full-width one that must sit alone at a page top), so it packs near
    # its reference instead of forcing the figure stream onto later pages.
    fig, axes = plt.subplots(len(scn_order), 1, figsize=(COL_W, 4.3),
                             sharey=True, sharex=True)
    axes = axes if len(scn_order) > 1 else [axes]
    step, x = 0.4, range(len(models))
    for ax, scn in zip(axes, scn_order, strict=False):
        for j, combo in enumerate(sub_order):
            label, hue = _SUBSTRATE[combo]
            cells = [
                out[(out["model"] == m) & (out["combo"] == combo)
                    & (out["scenario"] == scn)]
                for m in models
            ]
            vals = [c["pct_of_full"].sum() for c in cells]
            errs = [c["pct_of_full_ci"].sum() for c in cells]
            # peak remaining is a fraction of the full-network peak, so it cannot
            # exceed 100%; clamp the upper whisker at that ceiling (lower is free).
            lower = errs
            upper = [min(e, max(0.0, 100.0 - v)) for v, e in zip(vals, errs, strict=True)]
            ax.bar([xi + (j - 0.5) * step for xi in x], vals, step * BAR_GAP,
                   yerr=[lower, upper], error_kw=ERRKW, label=label, **_bar_kw(hue))
        ax.set_xticks(list(x))
        ax.set_xticklabels([_disease(m, two_line=True) for m in models])
        ax.tick_params(axis="x", labelsize=6.0)
        ax.set_title(_SCN[scn])
        ax.set_ylabel("peak remaining\n(% of full peak)")
        ax.axhline(100, ls="--", lw=0.6, color="#999", zorder=0)
    axes[0].legend(frameon=False, title="substrate", loc="upper left")
    fig.tight_layout()
    return _save(fig, "F-interdiction", out)


# --------------------------------------------------------------------------- #
# F-dose — dose-response: peak reduction vs cities vaccinated, both diseases.
# --------------------------------------------------------------------------- #
def fig_dose(summary: pd.DataFrame) -> Path | None:
    s = summary[(summary["region"] == REGION) & (summary["combo"] == FLAGSHIP)]
    if s.empty:
        return None
    hi = s[s["strategy"] != "control"]["coverage"].max()
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.5))
    out_rows, plotted = [], False
    for m in MODELS:
        sm = s[s["model"] == m]
        ctrl = sm[sm["strategy"] == "control"].groupby("seed")["peak_infected"].mean()
        ctrl = ctrl[ctrl > 0]
        cand = sm[(sm["strategy"] != "control") & (sm["coverage"] == hi)]
        if cand.empty or ctrl.empty:
            continue
        # Dose-response of the paper's winning rule, betweenness (lowest peak at the
        # operating budget for every disease). Selecting by "most budgets swept" is
        # unreliable once several strategies have been dose-swept across runs, so we
        # prefer betweenness where it has a sweep and fall back otherwise.
        swept = cand.groupby("strategy")["budget"].nunique()
        swept = swept[swept > 1]
        if swept.empty:
            continue
        winner = "betweenness" if "betweenness" in swept.index else swept.idxmax()
        wcand = cand[cand["strategy"] == winner]
        bvals, means, cis = [], [], []
        for b in sorted(wcand["budget"].unique()):
            peak = wcand[wcand["budget"] == b].groupby("seed")["peak_infected"].mean()
            paired = pd.concat([peak.rename("peak"), ctrl.rename("ctrl")],
                               axis=1, join="inner").dropna()
            if paired.empty:
                continue
            red_s = (paired["ctrl"] - paired["peak"]) / paired["ctrl"] * 100.0
            bvals.append(int(b))
            means.append(red_s.mean())
            cis.append(ci95(red_s))
        if len(bvals) < 2:
            continue
        means_a, cis_a = np.array(means), np.array(cis)
        hue = DISEASE_HUE[m]
        # lines take the darker stroke (pastel would vanish on white); markers
        # take the pastel fill with that stroke, so they match the bar figures.
        ax.plot(bvals, means_a, "-o", ms=4.5, color=EDGE[hue],
                markerfacecolor=FILL[hue], markeredgecolor=EDGE[hue],
                label=f"{_disease(m)}, {winner}")
        ax.fill_between(bvals, means_a - cis_a, means_a + cis_a,
                        color=FILL[hue], alpha=0.55, linewidth=0)
        plotted = True
        out_rows += [{"model": m, "strategy": winner, "budget": b,
                      "reduction_pct": r, "reduction_ci": c}
                     for b, r, c in zip(bvals, means, cis, strict=True)]
    if not plotted:
        return None
    ax.set_xlabel("cities vaccinated (budget)")
    ax.set_ylabel("peak reduction vs\nno vaccination (%)")
    ax.set_ylim(bottom=0)
    ax.set_title("Peak reduction vs. number of cities vaccinated")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, "F-dose", pd.DataFrame(out_rows))


# --------------------------------------------------------------------------- #
# F-deaths — deaths averted for the lethal SEIQRD type, per strategy (flagship).
# peak_infected hides case fatality (mu ~= 0.71), so this is the metric that makes
# the Ebola row meaningful. Deaths are read from each run's D compartment.
# --------------------------------------------------------------------------- #
def _draw_deaths(ax, region: str = REGION, budget: int = 15) -> pd.DataFrame | None:
    from src.evaluate.aggregate import deaths_table

    df = deaths_table(write=False)
    if df is None or df.empty:
        return None
    s = df[(df["region"] == region) & (df["combo"] == FLAGSHIP) & (df["budget"] == budget)]
    if s.empty:
        return None
    s = s[s["coverage"] == s["coverage"].max()]
    # per-capita, like F-spread: deaths averted per 100k of the flagship
    # population, so the lethal figure carries the same units as the rest of the
    # panel rather than a raw head-count. Population is the total_population the
    # engine records (constant per network), read from the summary table.
    summary = _read("summary.parquet")
    pop = float("nan")
    if summary is not None and not summary.empty:
        ps = summary[(summary["region"] == region) & (summary["combo"] == FLAGSHIP)]
        if not ps.empty:
            pop = float(ps["total_population"].iloc[0])
    if not (pop == pop and pop > 0):  # no population to normalise by
        return None
    strats = [x for x in STRAT_ORDER if x in set(s["strategy"])]
    rows = []
    for strat in strats:
        av = s[s["strategy"] == strat]["deaths_averted"].dropna() / pop * 1e5
        if av.empty:
            continue
        rows.append({"strategy": strat, "deaths_averted_per_100k": av.mean(), "ci": ci95(av)})
    if not rows:
        return None
    d = pd.DataFrame(rows)
    x = range(len(d))
    ax.bar(list(x), d["deaths_averted_per_100k"], BAR_GAP * 0.8, yerr=d["ci"],
           error_kw=ERRKW, **_bar_kw("purple"))
    ax.set_xticks(list(x))
    ax.set_xticklabels([_strat_label(s) for s in d["strategy"]], rotation=20, ha="right")
    ax.set_ylabel("deaths averted per 100k\n(vs no vaccination)")
    ax.set_title("Deaths averted, lethal type (SEIQRD)")
    return d


def fig_deaths(region: str = REGION, budget: int = 15) -> Path | None:
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.6))
    d = _draw_deaths(ax, region, budget)
    if d is None:
        plt.close(fig)
        return None
    return _save(fig, "F-deaths", d)


# --------------------------------------------------------------------------- #
# F-equity — where betweenness-targeting places protection, on real geography.
# Cities at their coordinates; the betweenness-selected set is shown in tiers at
# the three dose budgets (top 15 / 50 / 200), so the reader sees that protection
# spreads across the continent's countries rather than piling onto one nation's
# hubs, and how it extends outward as the budget grows. Pure structure.
# --------------------------------------------------------------------------- #
def _draw_equity(ax, region: str = REGION, combo: str = FLAGSHIP) -> pd.DataFrame | None:
    from collections import Counter

    from src.evaluate.centrality import betweenness
    from src.netgen.graph_io import read_graphml
    from src.paths import processed_graph

    if not processed_graph(region, combo).exists():
        return None
    g = read_graphml(processed_graph(region, combo))
    btw = betweenness(g)
    ranked = sorted(g.nodes(), key=lambda n: btw[n], reverse=True)
    lon = {n: float(g.nodes[n]["lon"]) for n in g.nodes()}
    lat = {n: float(g.nodes[n]["lat"]) for n in g.nodes()}
    ax.scatter([lon[n] for n in g.nodes()], [lat[n] for n in g.nodes()], s=2,
               color="#e2e2e2", zorder=1)  # all cities for geographic context
    # betweenness-selected set drawn in tiers at the three dose budgets; smaller
    # (higher-priority) tiers sit on top.
    tiers = [(50, 200, "yellow", 9, "ranks 51--200", 2),
             (15, 50, "orange", 24, "ranks 16--50", 3),
             (0, 15, "red", 55, "top 15 (operating budget)", 4)]
    for lo, hi, hue, size, label, z in tiers:
        sel = ranked[lo:hi]
        ax.scatter([lon[n] for n in sel], [lat[n] for n in sel], s=size,
                   color=FILL[hue], edgecolors=EDGE[hue], linewidths=0.5,
                   zorder=z, label=label)
    top15_countries = Counter(str(g.nodes[n].get("country", "?")) for n in ranked[:15])
    ax.axis("off")
    ax.set_aspect(1.4)
    ax.set_title(f"Betweenness-targeted protection: top 15 spans {len(top15_countries)} countries")
    handles, labels = ax.get_legend_handles_labels()
    # horizontal legend below the map so it never covers a city
    ax.legend(handles[::-1], labels[::-1], fontsize=6, ncol=3, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.01),
              handletextpad=0.3, columnspacing=1.0)
    rows = pd.DataFrame(
        {"rank": i + 1, "name": str(g.nodes[n].get("name", n)),
         "country": str(g.nodes[n].get("country", "?")), "betweenness": btw[n]}
        for i, n in enumerate(ranked[:200])
    )
    return rows


def fig_equity(region: str = REGION, combo: str = FLAGSHIP) -> Path | None:
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 3.3))
    rows = _draw_equity(ax, region, combo)
    if rows is None:
        plt.close(fig)
        return None
    return _save(fig, "F-equity", rows)


# --------------------------------------------------------------------------- #
# F-geo — the Europe network on real geography: cities at their coordinates,
# sized by population, coloured by betweenness, with the anomalous gateways
# (high-betweenness / modest-degree bridge cities) ringed. Air-only vs the
# multimodal flagship, so the land + ferry layers' peripheral bridges are the
# visible difference. Pure structure (no simulation).
# --------------------------------------------------------------------------- #
def fig_geo_map(region: str = REGION) -> Path | None:
    from src.evaluate.centrality import betweenness
    from src.evaluate.metrics import degree_betweenness
    from src.netgen.graph_io import read_graphml
    from src.paths import processed_graph

    combos = ["air", FLAGSHIP]
    graphs = {c: read_graphml(processed_graph(region, c)) for c in combos
              if processed_graph(region, c).exists()}
    if not graphs:
        return None
    present = [c for c in combos if c in graphs]
    _style()
    # maps stacked vertically at column width: a single-column float that packs
    # near its reference rather than a full-width one pinned to a page top.
    fig, axes = plt.subplots(len(present), 1, figsize=(COL_W, 5.6))
    axes = axes if len(present) > 1 else [axes]
    sc = None
    rows = []
    for ax, c in zip(axes, present, strict=True):
        g = graphs[c]
        btw = betweenness(g)
        anom = set(degree_betweenness(g)["anomalous_gateways"])
        nodes = list(g.nodes())
        lon = {n: float(g.nodes[n]["lon"]) for n in nodes}
        lat = {n: float(g.nodes[n]["lat"]) for n in nodes}
        for u, v in g.edges():
            ax.plot([lon[u], lon[v]], [lat[u], lat[v]],
                    color="#cccccc", lw=0.12, alpha=0.4, zorder=1)
        pops = np.array([float(g.nodes[n].get("population", 0) or 0) for n in nodes])
        sizes = 3 + 45 * (pops / pops.max() if pops.max() else np.zeros_like(pops))
        bvals = np.array([btw[n] for n in nodes])
        sc = ax.scatter([lon[n] for n in nodes], [lat[n] for n in nodes], s=sizes,
                        c=bvals, cmap="viridis", linewidths=0.15,
                        edgecolors="#333333", zorder=2)
        ring = [n for n in nodes if n in anom]
        ax.scatter([lon[n] for n in ring], [lat[n] for n in ring], s=55,
                   facecolors="none", edgecolors=EDGE["red"], linewidths=1.0, zorder=3)
        label = {"air": "air-only", FLAGSHIP: "multimodal"}.get(c, c)
        ax.set_title(f"{label}  (n={g.number_of_nodes()}, {len(ring)} gateways)")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect(1.4)
        rows.append({"combo": c, "n_nodes": g.number_of_nodes(), "n_anomalous": len(ring)})
    from matplotlib.lines import Line2D
    handle = Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="none",
                    markeredgecolor=EDGE["red"], markersize=8, markeredgewidth=1.2,
                    label="anomalous gateway (high betweenness, modest degree)")
    fig.legend(handles=[handle], loc="lower center", frameon=False, fontsize=7,
               bbox_to_anchor=(0.5, -0.02))
    if sc is not None:
        fig.colorbar(sc, ax=axes, fraction=0.045, pad=0.02, label="betweenness")
    return _save(fig, "F-geo", pd.DataFrame(rows))


# --------------------------------------------------------------------------- #
# F-curves — the epidemic curve I(t) itself: infectious fraction over time
# across the realism ladder (control, one disease), seed-median with an IQR
# band. Shows the peak HEIGHT and its TIMING / desynchronisation together, which
# the bar figures collapse to a single number. Reads the per-run time series.
# --------------------------------------------------------------------------- #
def _draw_curves(ax, summary: pd.DataFrame, model: str = "sir",
                 region: str = REGION) -> pd.DataFrame | None:
    from src.paths import run_timeseries

    sel = summary[(summary["region"] == region) & (summary["model"] == model)
                  & (summary["strategy"] == "control") & (summary["combo"].isin(RUNGS))]
    if sel.empty:
        return None
    rows, plotted, last_active = [], False, 0
    for combo in RUNGS:
        curves, pop = [], None
        for _, r in sel[sel["combo"] == combo].iterrows():
            tp = run_timeseries(region, combo, r["label"])
            if not tp.exists():
                continue
            try:
                ts = pd.read_parquet(tp, columns=["I"])
            except (OSError, ValueError, KeyError):
                continue
            curves.append(ts["I"].to_numpy())
            pop = r["total_population"]
        if not curves or not pop:
            continue
        length = min(len(c) for c in curves)
        mat = np.vstack([c[:length] for c in curves]) / pop * 100.0
        med = np.median(mat, axis=0)
        lo, hi = np.percentile(mat, [25, 75], axis=0)
        days = np.arange(length)
        # last day this rung is still meaningfully active (for cropping the flat
        # burnt-out tail; endemic types stay active so they are not cropped).
        active = np.where(med > 0.05)[0]
        if active.size:
            last_active = max(last_active, int(active[-1]))
        hue = RUNG_HUE[combo]
        ax.plot(days, med, color=EDGE[hue], lw=1.2, label=RUNG_LABEL[combo])
        ax.fill_between(days, lo, hi, color=FILL[hue], alpha=0.55, linewidth=0)
        plotted = True
        rows += [{"combo": combo, "day": int(d), "median_pct": float(m),
                  "p25": float(a), "p75": float(b)}
                 for d, m, a, b in zip(days, med, lo, hi, strict=True)]
    if not plotted:
        return None
    if last_active:  # zoom to the active window so a fast burnout is visible
        ax.set_xlim(0, last_active * 1.25)
    ax.set_xlabel("day")
    ax.set_ylabel("infectious (% of population)")
    ax.set_title(f"Epidemic curve across the realism ladder ({_disease(model)})")
    ax.legend(frameon=False, title="substrate")
    return pd.DataFrame(rows)


def fig_epicurves(summary: pd.DataFrame, model: str = "sir",
                  region: str = REGION) -> Path | None:
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.6))
    rows = _draw_curves(ax, summary, model, region)
    if rows is None:
        plt.close(fig)
        return None
    return _save(fig, "F-curves", rows)


# --------------------------------------------------------------------------- #
# F-scatter — degree vs betweenness per city (flagship), log axes, with the
# anomalous gateways ringed and Spearman rho annotated. The visual proof that
# high-degree cities are mostly the high-betweenness ones (why degree ~=
# betweenness as a target), and that the residual gap is carried by the few
# divergent bridge cities. Pure structure (no simulation).
# --------------------------------------------------------------------------- #
def fig_deg_btw_scatter(region: str = REGION, combo: str = FLAGSHIP) -> Path | None:
    from scipy.stats import spearmanr

    from src.evaluate.centrality import betweenness
    from src.evaluate.metrics import degree_betweenness
    from src.netgen.graph_io import read_graphml
    from src.paths import processed_graph

    if not processed_graph(region, combo).exists():
        return None
    g = read_graphml(processed_graph(region, combo))
    btw = betweenness(g)
    anom = set(degree_betweenness(g)["anomalous_gateways"])
    nodes = list(g.nodes())
    deg = np.array([g.degree(n) for n in nodes], dtype=float)
    bv = np.array([btw[n] for n in nodes], dtype=float)
    rho, _ = spearmanr(deg, bv)
    is_anom = np.array([n in anom for n in nodes])
    # betweenness is non-negative; floor the zeros (leaf cities) just below the
    # smallest positive value so a log axis can show them as a bottom row,
    # instead of a symlog axis wasting half the panel on impossible negatives.
    pmin = float(bv[bv > 0].min()) if (bv > 0).any() else 1e-6
    floor = pmin / 3.0
    bvp = np.where(bv > 0, bv, floor)
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.8))
    ax.scatter(deg[~is_anom], bvp[~is_anom], s=8, color=FILL["blue"],
               edgecolors=EDGE["blue"], linewidths=0.3, alpha=0.8, zorder=2)
    ax.scatter(deg[is_anom], bvp[is_anom], s=26, facecolors=FILL["red"],
               edgecolors=EDGE["red"], linewidths=0.8, zorder=3,
               label=f"anomalous gateway (n={int(is_anom.sum())})")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(floor * 0.6, float(bv.max()) * 1.6)
    ax.set_xlabel("degree")
    ax.set_ylabel("betweenness")
    ax.set_title(f"Degree vs betweenness (multilayer, $\\rho$={rho:.2f})")
    ax.legend(frameon=False, loc="upper left", fontsize=6)
    return _save(fig, "F-scatter", pd.DataFrame(
        {"node": nodes, "degree": deg, "betweenness": bv, "anomalous": is_anom}))


# --------------------------------------------------------------------------- #
# F-degdist — degree distribution as a complementary CDF, P(K>=k), drawn as a
# log-log scatter across the realism ladder. The CCDF is the standard power-law
# view (Clauset et al.): unlike the raw P(k), it has no 1/N tail floor, so the
# heavy tail reads honestly as a curve of points dropping toward the few
# highest-degree hubs. Pure structure (no simulation).
# --------------------------------------------------------------------------- #
def fig_degdist(region: str = REGION) -> Path | None:
    from src.netgen.graph_io import read_graphml
    from src.paths import processed_graph

    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.8))
    # distinct markers so the three overlaid rungs stay legible as points
    marker = {"air": "o", "air+water": "s", "air+land+water": "^"}
    rows, plotted = [], False
    for combo in RUNGS:
        if not processed_graph(region, combo).exists():
            continue
        g = read_graphml(processed_graph(region, combo))
        deg = np.array([d for _, d in g.degree()], dtype=float)
        deg = deg[deg > 0]
        if deg.size == 0:
            continue
        # CCDF at each distinct degree: fraction of nodes with degree >= k.
        k, counts = np.unique(deg, return_counts=True)
        ccdf = counts[::-1].cumsum()[::-1] / deg.size  # P(K >= k)
        hue = RUNG_HUE[combo]
        ax.scatter(k, ccdf, s=13, marker=marker.get(combo, "o"), color=FILL[hue],
                   edgecolors=EDGE[hue], linewidths=0.4, alpha=0.85,
                   label=RUNG_LABEL[combo])
        plotted = True
        rows += [{"combo": combo, "degree": float(kk), "ccdf": float(c)}
                 for kk, c in zip(k, ccdf, strict=True)]
    if not plotted:
        return None
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"degree $k$")
    ax.set_ylabel(r"fraction of nodes with degree $\geq k$")
    ax.set_title("Degree distribution (CCDF) across the realism ladder")
    ax.legend(frameon=False, title="substrate")
    return _save(fig, "F-degdist", pd.DataFrame(rows))


# --------------------------------------------------------------------------- #
# Appendix figures — the full per-seed distributions behind the headline means.
# The main figures show mean +/- 95% CI; these show the underlying ensemble
# spread (box = median + IQR, whiskers, every seed as a jittered point), so the
# error bars are auditable and any skew or outlier seed is visible. Each drops a
# CSV of the raw per-seed values. Rendered only when the ensemble has >= 2 seeds.
# --------------------------------------------------------------------------- #
def _box(ax, values, position: float, hue: str, width: float) -> None:
    """One pastel box (matching the bar palette) with the seeds jittered over it,
    for a single cell. ``values`` is that cell's per-seed array."""
    bp = ax.boxplot([values], positions=[position], widths=width,
                    patch_artist=True, showfliers=False, manage_ticks=False)
    for box in bp["boxes"]:
        box.set(facecolor=FILL[hue], edgecolor=EDGE[hue], linewidth=BAR_LW)
    for part in ("whiskers", "caps", "medians"):
        for ln in bp[part]:
            ln.set(color=EDGE[hue], linewidth=BAR_LW)
    jit = np.random.default_rng(0).normal(position, width * 0.18, size=len(values))
    ax.scatter(jit, values, s=4, color=EDGE[hue], alpha=0.5, zorder=3)


def fig_app_peak_dist(summary: pd.DataFrame) -> Path | None:
    """Appendix: per-seed distribution of the peak (as % of population) for every
    disease across the realism ladder — the ensemble spread behind F-spread's
    bars. Makes clear that, e.g., the milder types genuinely peak near a few per
    cent while SIR runs hot, rather than any single '26% ceiling'."""
    df = summary[(summary["region"] == REGION) & (summary["strategy"] == "control")]
    df = df[df["combo"].isin(RUNGS)].copy()
    if df.empty or df["seed"].nunique() < 2:
        return None
    df["peak_pct"] = df["peak_infected"] / df["total_population"] * 100.0
    models = [m for m in MODELS if m in df["model"].unique()]
    _style()
    fig, ax = plt.subplots(figsize=(WIDE, 2.8))
    step, x = 0.27, list(range(len(models)))
    rows = []
    for i, rung in enumerate(RUNGS):
        for xi, m in zip(x, models, strict=True):
            sub = df[(df["model"] == m) & (df["combo"] == rung)][["seed", "peak_pct"]].dropna()
            if sub.empty:
                continue
            pos = xi + (i - 1) * step
            _box(ax, sub["peak_pct"].values, pos, RUNG_HUE[rung], step * BAR_GAP)
            rows += [{"model": m, "combo": rung, "seed": int(sd), "peak_pct": float(v)}
                     for sd, v in zip(sub["seed"], sub["peak_pct"], strict=True)]
    ax.set_xticks(x)
    ax.set_xticklabels([_disease(m, two_line=True) for m in models])
    ax.set_ylabel("peak infected (% of population)")
    ax.set_title("Per-seed peak distribution across the realism ladder")
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=FILL[RUNG_HUE[r]],
                             edgecolor=EDGE[RUNG_HUE[r]], linewidth=BAR_LW)
               for r in RUNGS]
    ax.legend(handles, [RUNG_LABEL[r] for r in RUNGS], frameon=False,
              title="substrate", loc="upper right")
    return _save(fig, "A-peak-dist", pd.DataFrame(rows))


def fig_app_gap_dist(summary: pd.DataFrame) -> Path | None:
    """Appendix: per-seed distribution of the degree- vs betweenness-targeting
    peak gap (relative) at the flagship, per disease. Positive = betweenness beats
    degree; a box straddling zero means the two tie for that disease. Paired per
    seed (both strategies share the seed's initial placement)."""
    s = summary[(summary["region"] == REGION) & (summary["combo"] == FLAGSHIP)]
    s = s[s["strategy"].isin(["degree", "betweenness"])]
    if s.empty or s["seed"].nunique() < 2:
        return None
    s = s[s["coverage"] == s["coverage"].max()]
    piv = (s.groupby(["model", "seed", "strategy"])["peak_infected"].mean()
             .unstack("strategy"))
    if not {"degree", "betweenness"}.issubset(piv.columns):
        return None
    piv = piv.dropna(subset=["degree", "betweenness"])
    piv["gap_rel"] = (piv["degree"] - piv["betweenness"]) / piv["degree"] * 100.0
    models = [m for m in MODELS if m in piv.index.get_level_values("model")]
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.8))
    rows = []
    for xi, m in enumerate(models):
        vals = piv.xs(m, level="model")["gap_rel"].dropna()
        if vals.empty:
            continue
        _box(ax, vals.values, xi, DISEASE_HUE[m], 0.5)
        rows += [{"model": m, "gap_rel_pct": float(v)} for v in vals]
    ax.axhline(0, ls="--", lw=0.6, color="#999", zorder=0)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([_disease(m, two_line=True) for m in models])
    ax.set_ylabel("degree − betweenness\npeak gap (% of degree peak)")
    ax.set_title("Per-seed degree-vs-betweenness gap (flagship)")
    return _save(fig, "A-gap-dist", pd.DataFrame(rows))


# --------------------------------------------------------------------------- #
# Merged two-panel figures. The spread bars and the epidemic curve are one story
# (how each disease spreads, Section 3.2); the deaths bars and the protection map
# are another (deaths averted and where protection lands, Section 3.6). Pairing
# them keeps each results page from stacking three separate floats.
# --------------------------------------------------------------------------- #
def fig_spread_curves(summary: pd.DataFrame) -> Path | None:
    # panels stacked vertically at column width, so this stays a single-column
    # float (top OR bottom of a column) that sits near its reference rather than
    # queuing for a page top like a full-width figure.
    _style()
    fig, (axa, axb) = plt.subplots(2, 1, figsize=(COL_W, 4.4))
    g = _draw_spread(axa, summary)
    r = _draw_curves(axb, summary)
    if g is None or r is None:
        plt.close(fig)
        return None
    axa.set_title("(a) Peak active infection by substrate", fontsize=8.5)
    axb.set_title("(b) Measles epidemic curve (SIR)", fontsize=8.5)
    leg = axa.get_legend()  # drop the bars' below-axis legend; panel (b) keeps one
    if leg is not None:
        leg.remove()
    fig.tight_layout()
    return _save(fig, "F-spread-curves", g)


def fig_deaths_equity(region: str = REGION, budget: int = 15,
                      combo: str = FLAGSHIP) -> Path | None:
    _style()
    fig, (axa, axb) = plt.subplots(2, 1, figsize=(COL_W, 4.7),
                                   gridspec_kw={"height_ratios": [0.85, 1.5]})
    d = _draw_deaths(axa, region, budget)
    rows = _draw_equity(axb, region, combo)
    if d is None or rows is None:
        plt.close(fig)
        return None
    axa.set_title("(a) Deaths averted, lethal type (SEIQRD)", fontsize=8.5)
    axb.set_title("(b) Where betweenness places protection", fontsize=8.5)
    fig.tight_layout()
    return _save(fig, "F-deaths-equity", d)


# --------------------------------------------------------------------------- #
def build_all(echo=print) -> list[Path]:
    """Build the curated result figures whose backing data is present."""
    made: list[Path] = []

    def _try(label, fn):
        try:
            out = fn()
        except FileNotFoundError:
            out = None
        if out is None:
            echo(f"  skip {label}: data not available yet")
        else:
            made.append(out)
            echo(f"  wrote {out.relative_to(ROOT)}")

    summary = _read("summary.parquet")
    if summary is not None:
        _try("F-spread-curves", lambda: fig_spread_curves(summary))
        _try("F-defense", lambda: fig_defense(summary))
        _try("F-dose", lambda: fig_dose(summary))
    _try("F-interdiction", fig_interdiction)
    _try("F-deaths-equity", fig_deaths_equity)
    _try("F-geo", fig_geo_map)
    _try("F-scatter", fig_deg_btw_scatter)
    _try("F-degdist", fig_degdist)
    if summary is not None:  # appendix: full per-seed distributions
        _try("A-peak-dist", lambda: fig_app_peak_dist(summary))
        _try("A-gap-dist", lambda: fig_app_gap_dist(summary))
    return made


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

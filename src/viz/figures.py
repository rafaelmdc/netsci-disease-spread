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

Backing data: results/summary.parquet and the per-disease two-substrate
results/<region>/air+land+water/interdiction_<model>.parquet files.
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
STRAT_ORDER = ["random", "degree", "betweenness", "subgraph"]


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


def _millions(x: float, _pos=None) -> str:
    return f"{x / 1e6:.0f}M" if x >= 1e6 else f"{x / 1e3:.0f}k"


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
def fig_spread(summary: pd.DataFrame) -> Path | None:
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
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.5))
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
    _style()
    # Full text width: five diseases per strategy need room, so this is a wide
    # (double-column) figure. Bar width is sized to n diseases so a strategy's
    # group spans <1.0 and never collides with the neighbouring strategy.
    fig, ax = plt.subplots(figsize=(WIDE, 2.7))
    n = len(models)
    step = min(0.16, 0.82 / n)
    x = range(len(STRAT_ORDER))
    for j, m in enumerate(models):
        off = (j - (n - 1) / 2) * step  # centre the group on each tick
        cells = [red[(red["model"] == m) & (red["strategy"] == s)] for s in STRAT_ORDER]
        vals = [c["reduction_pct"].sum() for c in cells]
        errs = [c["reduction_ci"].sum() for c in cells]
        ax.bar([xi + off for xi in x], vals, step * BAR_GAP,
               yerr=errs, error_kw=ERRKW,
               label=_disease(m), **_bar_kw(DISEASE_HUE[m]))
    ax.set_xticks(list(x))
    ax.set_xticklabels(STRAT_ORDER)
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
    fig, axes = plt.subplots(1, len(scn_order), figsize=(WIDE, 2.7), sharey=True)
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
            ax.bar([xi + (j - 0.5) * step for xi in x], vals, step * BAR_GAP,
                   yerr=errs, error_kw=ERRKW, label=label, **_bar_kw(hue))
        ax.set_xticks(list(x))
        ax.set_xticklabels([_disease(m, two_line=True) for m in models])
        ax.set_title(_SCN[scn])
        ax.axhline(100, ls="--", lw=0.6, color="#999", zorder=0)
    axes[0].set_ylabel("peak remaining\n(% of full-network peak)")
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
        winner = cand.groupby("strategy")["budget"].nunique().idxmax()
        wcand = cand[cand["strategy"] == winner]
        bvals, means, cis = [], [], []
        for b in sorted(wcand["budget"].unique()):
            peak = wcand[wcand["budget"] == b].groupby("seed")["peak_infected"].mean()
            paired = pd.concat([peak.rename("peak"), ctrl.rename("ctrl")],
                               axis=1, join="inner").dropna()
            if paired.empty:
                continue
            red_s = (paired["ctrl"] - paired["peak"]) / paired["ctrl"] * 100.0
            bvals.append(int(b)); means.append(red_s.mean()); cis.append(ci95(red_s))
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
                     for b, r, c in zip(bvals, means, cis)]
    if not plotted:
        return None
    ax.set_xlabel("cities vaccinated (budget)")
    ax.set_ylabel("peak reduction vs\nno vaccination (%)")
    ax.set_ylim(bottom=0)
    ax.set_title("Peak reduction vs. number of cities vaccinated")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, "F-dose", pd.DataFrame(out_rows))


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
        _try("F-spread", lambda: fig_spread(summary))
        _try("F-defense", lambda: fig_defense(summary))
        _try("F-dose", lambda: fig_dose(summary))
    _try("F-interdiction", fig_interdiction)
    return made


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

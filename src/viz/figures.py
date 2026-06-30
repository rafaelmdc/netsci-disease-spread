"""Static, paper-ready result figures (matplotlib -> vector PDF/SVG).

Distinct from the ``*_html`` generators, which build the interactive Plotly
explorer. These read the collected tables in ``results/`` and write column-width
vector figures into ``docs/tex/`` for the article. Each figure also drops a
small CSV of the exact numbers it plots, so the figure is reproducible.

  F4  region spectrum        structure.parquet (+ a built graph for the scatter)
  F5  Europe spread ladder   summary.parquet (control runs)
  F6  vaccination panel      summary.parquet (anchor disease x strategy x rung)
  F6b degree-vs-betweenness   strategy_gap.parquet
  Fstaged  the staged story  summary.parquet (stage-2 ranking + stage-3 check)
  F7  interdiction A-D       results/<region>/<combo>/interdiction.parquet
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed
import matplotlib.pyplot as plt
import pandas as pd

from src.paths import RESULTS, ROOT

TEX = ROOT / "docs" / "tex"
COL_W = 3.4  # one column of a double-column page (inches)
WIDE = 7.0  # full text width

# realism ladder, in order (water added before land), light->dark palette
RUNGS = ["air", "air+water", "air+land+water"]
RUNG_LABEL = {"air": "air", "air+water": "+water", "air+land+water": "+land"}
RUNG_COLOR = {"air": "#9ecae1", "air+water": "#4292c6", "air+land+water": "#084594"}
STRAT_COLOR = {
    "control": "#bdbdbd", "random": "#fdae6b", "degree": "#74c476",
    "betweenness": "#6baed6", "subgraph": "#9e9ac8", "kcore": "#fb6a4a",
}
# Disease TYPE label per model, so figures read as diseases (all five supported).
DISEASE = {
    "sir": "Measles", "sis": "Gonorrhea", "seir": "COVID",
    "seirs": "Flu", "seiqrd": "Ebola", "sqir": "SQIR",
}


def _disease(model: str, two_line: bool = False) -> str:
    name = DISEASE.get(model, model.upper())
    sep = "\n" if two_line else " "
    return f"{name}{sep}({model.upper()})" if model in DISEASE else name


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
# F5 — Europe spread ladder: how the outbreak grows as realism is added.
# --------------------------------------------------------------------------- #
def fig_spread_ladder(summary: pd.DataFrame) -> Path | None:
    df = summary[(summary["region"] == "europe") & (summary["strategy"] == "control")]
    df = df[df["combo"].isin(RUNGS)]
    if df.empty:
        return None
    g = df.groupby(["model", "combo"])["peak_infected"].mean().reset_index()
    models = sorted(g["model"].unique())
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.4))
    width, x = 0.26, range(len(models))
    for i, rung in enumerate(RUNGS):
        vals = [
            g[(g["model"] == m) & (g["combo"] == rung)]["peak_infected"].sum()
            for m in models
        ]
        ax.bar([xi + (i - 1) * width for xi in x], vals, width,
               label=RUNG_LABEL[rung], color=RUNG_COLOR[rung])
    ax.set_xticks(list(x))
    ax.set_xticklabels([_disease(m, two_line=True) for m in models])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
    ax.set_ylabel("peak active infections")
    ax.set_title("Europe: peak outbreak by disease and realism")
    ax.legend(title="substrate", frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.18))
    return _save(fig, "F5-spread-ladder", g)


# --------------------------------------------------------------------------- #
# F6 — Vaccination on the anchor disease: strategy per rung (one coverage).
# --------------------------------------------------------------------------- #
def fig_vaccination_panel(summary: pd.DataFrame, anchor: str = "seir") -> Path | None:
    df = summary[(summary["region"] == "europe") & (summary["model"] == anchor)]
    df = df[df["combo"].isin(RUNGS)]
    if df.empty:
        return None
    rungs = [r for r in RUNGS if r in df["combo"].unique()]
    hi = df[df["strategy"] != "control"]["coverage"].max()  # the operating coverage
    order = ["control", "random", "degree", "betweenness", "subgraph"]
    present = set(df["strategy"].unique())
    strats = [s for s in order if s in present]
    _style()
    fig, axes = plt.subplots(1, len(rungs), figsize=(WIDE, 2.4), sharey=True)
    axes = axes if len(rungs) > 1 else [axes]
    for ax, rung in zip(axes, rungs, strict=False):
        sub = df[df["combo"] == rung]
        ctrl = sub[sub["strategy"] == "control"]["peak_infected"].mean()
        vals = [
            ctrl if s == "control"
            else sub[(sub["strategy"] == s) & (sub["coverage"] == hi)]["peak_infected"].mean()
            for s in strats
        ]
        ax.bar(range(len(strats)), vals,
               color=[STRAT_COLOR.get(s, "#6baed6") for s in strats])
        if pd.notna(ctrl):
            ax.axhline(ctrl, ls="--", lw=0.7, color="#888", zorder=0)
        ax.set_xticks(range(len(strats)))
        ax.set_xticklabels(strats, rotation=40, ha="right")
        ax.set_title(RUNG_LABEL[rung])
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
    axes[0].set_ylabel("peak active infections")
    cov_txt = f"{hi:.0%} coverage" if pd.notna(hi) else ""
    fig.suptitle(f"Vaccination on {_disease(anchor)} ({cov_txt}): strategy across "
                 f"the realism ladder", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _save(fig, "F6-vaccination-panel", df)


# --------------------------------------------------------------------------- #
# F6b — Degree vs betweenness: the gap that says 'bridges, not just hubs'.
# --------------------------------------------------------------------------- #
def fig_degbtw_gap(gap: pd.DataFrame, anchor: str = "seir") -> Path | None:
    df = gap[(gap["region"] == "europe") & (gap["model"] == anchor)]
    df = df[df["combo"].isin(RUNGS)]
    if df.empty:
        return None
    hi = df["coverage"].max()
    df = df[df["coverage"] == hi]
    g = df.groupby("combo")["gap_rel"].mean().reindex(RUNGS).dropna()
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.2))
    ax.bar([RUNG_LABEL[c] for c in g.index], g.values * 100,
           color=[RUNG_COLOR[c] for c in g.index])
    ax.axhline(0, lw=0.6, color="#444")
    ax.set_ylabel("peak reduction, betweenness\nover degree (%)")
    ax.set_title(f"Bridges vs hubs ({anchor.upper()}, {hi:.0%} coverage)")
    return _save(fig, "F6b-degree-betweenness-gap", g.reset_index())


# --------------------------------------------------------------------------- #
# Fstaged — the coordinate-descent story: stage-2 ranking + stage-3 check.
# --------------------------------------------------------------------------- #
def fig_staged_story(summary: pd.DataFrame, anchor: str = "seir",
                     flagship: str = "air+land+water") -> Path | None:
    s = summary[(summary["region"] == "europe") & (summary["model"] == anchor)]
    vacc = s[s["strategy"] != "control"]
    if vacc.empty:
        return None
    hi = vacc["coverage"].max()
    ranking = (vacc[vacc["coverage"] == hi].groupby("strategy")["peak_infected"]
               .mean().sort_values())
    winner = ranking.index[0]

    others = summary[(summary["region"] == "europe") & (summary["combo"] == flagship)
                     & (summary["model"] != anchor)]
    _style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDE, 2.5))

    ax1.barh([s for s in ranking.index][::-1], [v for v in ranking.values][::-1],
             color=["#08519c" if s == winner else "#9ecae1" for s in ranking.index][::-1])
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(_millions))
    ax1.set_xlabel("mean peak (anchor disease)")
    ax1.set_title(f"Stage 2: pick the winner on {_disease(anchor)}\n(winner: {winner})")

    if not others.empty:
        comp = (others[others["strategy"].isin(["control", winner])]
                .groupby(["model", "strategy"])["peak_infected"].mean().unstack("strategy"))
        comp = comp.reindex(columns=["control", winner]).dropna(how="all")
        models = list(comp.index)
        x = range(len(models))
        for j, col in enumerate(["control", winner]):
            if col not in comp:
                continue
            ax2.bar([xi + (j - 0.5) * 0.4 for xi in x], comp[col].values, 0.4,
                    label=col, color="#bdbdbd" if col == "control" else "#08519c")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels([_disease(m, two_line=True) for m in models])
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
        ax2.set_ylabel("peak active infections")
        ax2.set_title(f"Stage 3: does '{winner}' generalise?\n"
                      f"(other diseases, {RUNG_LABEL[flagship]})")
        ax2.legend(frameon=False)
    fig.tight_layout()
    return _save(fig, "Fstaged-coordinate-descent", ranking.reset_index())


# --------------------------------------------------------------------------- #
# F4 — Region spectrum: cross-region rho + a degree-betweenness scatter.
# --------------------------------------------------------------------------- #
def fig_region_spectrum(structure: pd.DataFrame, scatter_region: str = "europe") -> Path | None:
    # `evaluate structure` writes air-only rows without a combo column; the
    # aggregate writer adds one. Handle both.
    air = structure[structure["combo"] == "air"] if "combo" in structure else structure
    air = air.copy()
    if air.empty:
        return None
    air = air.sort_values("spearman_deg_btw")
    _style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDE, 2.6),
                                   gridspec_kw={"width_ratios": [1.2, 1]})

    # left: degree vs betweenness scatter for one representative network
    try:
        from src.evaluate.centrality import betweenness
        from src.evaluate.metrics import degree_betweenness
        from src.netgen.graph_io import read_graphml
        from src.paths import processed_graph
        graph = read_graphml(processed_graph(scatter_region, "air"))
        btw = betweenness(graph)
        deg = dict(graph.degree())
        anom = set(degree_betweenness(graph)["anomalous_gateways"])
        xs = [deg[n] for n in graph.nodes]
        ys = [btw[n] for n in graph.nodes]
        cols = ["#d62728" if n in anom else "#6baed6" for n in graph.nodes]
        ax1.scatter(xs, ys, s=8, c=cols, alpha=0.7, linewidths=0)
        ax1.set_xlabel("degree (how busy)")
        ax1.set_ylabel("betweenness (how much a bridge)")
        ax1.set_title(f"{scatter_region.capitalize()} air: busy vs bridge")
    except Exception:  # noqa: BLE001
        ax1.set_visible(False)

    # right: rho per region (the spectrum), correlated -> anomalous
    ax2.barh(air["region"].str.capitalize(), air["spearman_deg_btw"],
             color="#4292c6")
    ax2.set_xlabel(r"$\rho$(degree, betweenness)")
    ax2.set_title("Region spectrum:\ncorrelated -> anomalous")
    fig.tight_layout()
    return _save(fig, "F4-region-spectrum", air)


# --------------------------------------------------------------------------- #
# F7 — Interdiction A-D: grounding flights vs. the multilayer reality.
# --------------------------------------------------------------------------- #
def fig_interdiction(region: str = "europe") -> Path | None:
    from src.paths import network_figure

    panels = [("air", "Air only"), ("air+land+water", "Air + land + water")]
    series = {}
    for combo, _ in panels:
        p = network_figure(region, combo, "interdiction.parquet")
        if p.exists():
            series[combo] = pd.read_parquet(p)
    if not series:
        return None
    _style()
    fig, axes = plt.subplots(1, len(series), figsize=(WIDE, 2.6), sharey=True)
    axes = axes if len(series) > 1 else [axes]
    have = [(c, t) for c, t in panels if c in series]
    for ax, (combo, title) in zip(axes, have, strict=False):
        df = series[combo]
        for name, grp in df.groupby("scenario"):
            grp = grp.sort_values("day")
            ax.plot(grp["day"], grp["infectious"], lw=1.1, label=name.split(" · ")[0])
        ax.set_title(title)
        ax.set_xlabel("day")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_millions))
    axes[0].set_ylabel("active infections")
    axes[-1].legend(frameon=False, fontsize=6, title="scenario")
    fig.suptitle("Interdiction: grounding flights only contains it when air is the sole carrier",
                 fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, "F7-interdiction", pd.concat(series.values()))


# --------------------------------------------------------------------------- #
# F8 — Dose-response: how many cities must we vaccinate for a great reduction?
# --------------------------------------------------------------------------- #
def fig_dose_response(summary: pd.DataFrame, anchor: str = "sir",
                      flagship: str = "air+land+water") -> Path | None:
    s = summary[(summary["region"] == "europe") & (summary["model"] == anchor)
                & (summary["combo"] == flagship)]
    if s.empty:
        return None
    hi = s[s["strategy"] != "control"]["coverage"].max()
    cand = s[(s["strategy"] != "control") & (s["coverage"] == hi)]
    if cand.empty:
        return None
    # the dose stage sweeps budget for one strategy: pick the one with most budgets
    winner = cand.groupby("strategy")["budget"].nunique().idxmax()
    w = (cand[cand["strategy"] == winner].groupby("budget")["peak_infected"]
         .mean().sort_index())
    if len(w) < 2:
        return None  # no budget sweep present yet
    ctrl = s[s["strategy"] == "control"]["peak_infected"].mean()
    reduction = (ctrl - w.to_numpy()) / ctrl * 100.0
    _style()
    fig, ax = plt.subplots(figsize=(COL_W, 2.4))
    ax.plot(w.index, reduction, "-o", color="#08519c", ms=4)
    ax.set_xlabel("cities vaccinated (budget)")
    ax.set_ylabel("peak reduction vs no\nvaccination (%)")
    ax.set_ylim(0, max(5, reduction.max() * 1.15))
    ax.set_title(f"How many cities? {_disease(anchor)}, "
                 f"{winner} ({RUNG_LABEL[flagship]})")
    out = pd.DataFrame({"budget": w.index, "peak": w.to_numpy(), "reduction_pct": reduction})
    return _save(fig, "F8-dose-response", out)


# --------------------------------------------------------------------------- #
def build_all(anchor: str = "seir", echo=print) -> list[Path]:
    """Build every result figure whose backing table is present."""
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
    structure = _read("structure.parquet")
    gap = _read("strategy_gap.parquet")

    if structure is not None:
        _try("F4 region spectrum", lambda: fig_region_spectrum(structure))
    if summary is not None:
        _try("F5 spread ladder", lambda: fig_spread_ladder(summary))
        _try("F6 vaccination panel", lambda: fig_vaccination_panel(summary, anchor))
        _try("Fstaged story", lambda: fig_staged_story(summary, anchor))
    if gap is not None:
        _try("F6b degree-vs-betweenness", lambda: fig_degbtw_gap(gap, anchor))
    if summary is not None:
        _try("F8 dose-response", lambda: fig_dose_response(summary, anchor))
    _try("F7 interdiction", lambda: fig_interdiction())
    return made


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

"""Paper tables: LaTeX (booktabs) + CSV into ``docs/tex/``.

Companion to figures.py. Most tables are derived from the collected result
tables in ``results/``; T1 (the disease archetypes) is curated, since its
example diseases and literature sources are editorial, not computed.

  T1  disease archetypes        curated (models + example disease + R0 + sources)
  T2  region structure          structure.parquet
  T3  Europe spread ladder       summary.parquet (control runs)
  T4  vaccination ranking        summary.parquet (anchor disease)
  T5  interdiction A-D peaks     interdiction.parquet (air vs multimodal)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.paths import RESULTS, ROOT

TEX = ROOT / "docs" / "tex"
RUNGS = ["air", "air+land", "air+land+water"]
RUNG_LABEL = {"air": "air", "air+land": "+land", "air+land+water": "+water"}


def _write(df: pd.DataFrame, name: str, caption: str, label: str,
           floats: str = "{:,.0f}".format) -> Path:
    TEX.mkdir(parents=True, exist_ok=True)
    df.to_csv(TEX / f"{name}.csv", index=False)
    # escape=False: headers/cells may carry intentional LaTeX (math, \%). Data
    # columns here are numbers and controlled labels, so this is safe.
    tex = df.to_latex(
        index=False, escape=False, na_rep="--", float_format=floats,
        caption=caption, label=label, position="t",
    )
    tex = tex.replace("\\begin{table}[t]", "\\begin{table}[t]\n\\centering")
    path = TEX / f"{name}.tex"
    path.write_text(tex)
    return path


# T1 — disease archetypes (curated). Edit here; sources live in disease-types.md.
_ARCHETYPES = [
    ("SIR", "Measles-like", "acute, immunising", "12-18", "remove after recovery"),
    ("SIS", "Common-cold-like", "endemic, no immunity", "1.2-1.5", "return to susceptible"),
    ("SEIR", "COVID-like", "latent then infectious", "2.5-3.0", "incubation compartment"),
    ("SEIRS", "Influenza-like", "waning immunity", "1.3-1.8", "immunity wanes (R->S)"),
    ("SEIQRD", "Ebola-like", "latency, isolation, death", "1.5-2.5", "quarantine + fatality"),
]


def table_archetypes() -> Path:
    df = pd.DataFrame(
        _ARCHETYPES,
        columns=["Model", "Example disease", "Dynamics", "$R_0$ (lit.)", "Key feature"],
    )
    return _write(df, "T1-disease-archetypes",
                  "Disease archetypes as compartmental model types. Parameter "
                  "values and sources are given in the text.", "tab:archetypes")


def table_region_structure(structure: pd.DataFrame) -> Path | None:
    air = structure[structure["combo"] == "air"].copy()
    if air.empty:
        return None
    air = air.sort_values("spearman_deg_btw", ascending=False)
    cols = {"region": "Region", "n_nodes": "Cities", "mean_degree": "Mean deg.",
            "spearman_deg_btw": r"$\rho$(deg,btw)", "n_anomalous": "Gateways"}
    keep = [c for c in cols if c in air.columns]
    df = air[keep].rename(columns=cols)
    df["Region"] = df["Region"].str.capitalize()
    return _write(df, "T2-region-structure",
                  "Air-network structure per region, ordered from most "
                  "degree/betweenness-correlated to most anomalous.",
                  "tab:structure", floats="{:.2f}".format)


def table_spread_ladder(summary: pd.DataFrame) -> Path | None:
    df = summary[(summary["region"] == "europe") & (summary["strategy"] == "control")]
    df = df[df["combo"].isin(RUNGS)]
    if df.empty:
        return None
    piv = (df.groupby(["model", "combo"])["peak_infected"].mean()
           .unstack("combo").reindex(columns=RUNGS))
    piv = piv.rename(columns=RUNG_LABEL).reset_index().rename(columns={"model": "Model"})
    piv["Model"] = piv["Model"].str.upper()
    return _write(piv, "T3-spread-ladder",
                  "Europe peak active infections by disease as realism is added "
                  "(mean over seeds).", "tab:spread")


def table_vaccination(summary: pd.DataFrame, anchor: str = "seir") -> Path | None:
    s = summary[(summary["region"] == "europe") & (summary["model"] == anchor)
                & (summary["combo"] == "air+land+water")]
    if s.empty:
        return None
    ctrl = s[s["strategy"] == "control"]["peak_infected"].mean()
    hi = s[s["strategy"] != "control"]["coverage"].max()
    vacc = s[(s["strategy"] != "control") & (s["coverage"] == hi)]
    g = vacc.groupby("strategy")["peak_infected"].mean().sort_values()
    df = g.reset_index().rename(columns={"strategy": "Strategy", "peak_infected": "Peak"})
    df["Reduction"] = ((ctrl - df["Peak"]) / ctrl * 100).map("{:.0f}\\%".format)
    df["Strategy"] = df["Strategy"].str.capitalize()
    return _write(df, "T4-vaccination-ranking",
                  f"Vaccination on the {anchor.upper()} flagship (air+land+water, "
                  f"{hi * 100:.0f}\\% coverage): peak and reduction vs.\\ no "
                  f"vaccination (control peak {ctrl:,.0f}).", "tab:vacc")


def table_interdiction(region: str = "europe") -> Path | None:
    from src.paths import network_figure

    rows = []
    for combo in ("air", "air+land+water"):
        p = network_figure(region, combo, "interdiction.parquet")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        peaks = df.groupby("scenario")["infectious"].max()
        for scenario, peak in peaks.items():
            rows.append({"Scenario": scenario, RUNG_LABEL.get(combo, combo): peak})
    if not rows:
        return None
    merged = (pd.DataFrame(rows).groupby("Scenario").first().reset_index())
    return _write(merged, "T5-interdiction",
                  "Peak active infections under interdiction scenarios A--D, on "
                  "the air-only vs.\\ multilayer substrate.", "tab:interdiction")


def build_all(anchor: str = "seir", echo=print) -> list[Path]:
    made: list[Path] = []

    def _try(label, fn):
        out = fn()
        if out is None:
            echo(f"  skip {label}: data not available yet")
        else:
            made.append(out)
            echo(f"  wrote {out.relative_to(ROOT)}")

    structure = _read("structure.parquet")
    summary = _read("summary.parquet")

    _try("T1 archetypes", table_archetypes)
    if structure is not None:
        _try("T2 region structure", lambda: table_region_structure(structure))
    if summary is not None:
        _try("T3 spread ladder", lambda: table_spread_ladder(summary))
        _try("T4 vaccination", lambda: table_vaccination(summary, anchor))
    _try("T5 interdiction", lambda: table_interdiction())
    return made


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

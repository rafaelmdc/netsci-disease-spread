"""Paper tables into ``docs/curated_tex/figures/``.

Companion to figures.py. The result tables that merely re-printed a figure's
numbers (spread ladder, vaccination ranking, interdiction peaks, dose-response)
were dropped as duplication; the figures carry those. The one table we keep is
T1, the disease archetypes, which is editorial (example diseases + literature
$R_0$), not computed, and is the reference for the five types of which the
experiments test the two extremes (SIR, SIS).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.paths import RESULTS, ROOT

TEX = ROOT / "docs" / "curated_tex" / "figures"

# T1 — the disease types (curated). Defined by dynamical structure + exemplar.
# Edit here; parameter values and sources live in disease-types.md / Appendix A.
_T1 = r"""\begin{table*}[tp]
\centering
\caption{The disease types studied. Each type is defined by its dynamical structure (its
compartmental model) and parameterised from one representative exemplar disease. Numeric parameter
values and their literature sources are given in Appendix~\ref{app:sources}
(Tables~\ref{tab:params-values} and~\ref{tab:sources}).}
\label{tab:archetypes}
\begin{tabular}{llll l}
\toprule
\# & Type & Model & Example diseases & Parameters from \\
\midrule
1 & Immunizing, acute            & SIR    & measles, rubella, mumps          & measles \\
2 & Latent $+$ immunizing        & SEIR   & COVID-19, SARS, chickenpox       & COVID-19 \\
3 & Lethal, isolation-controlled & SEIQRD & Ebola, Marburg, pneumonic plague & Ebola \\
4 & Endemic, no immunity         & SIS    & gonorrhea, chlamydia, common cold & gonorrhea \\
5 & Recurrent, waning immunity & SEIRS & seasonal influenza, RSV, norovirus & seasonal influenza \\
\bottomrule
\end{tabular}
\end{table*}
"""


def table_archetypes() -> Path:
    TEX.mkdir(parents=True, exist_ok=True)
    path = TEX / "T1-disease-archetypes.tex"
    path.write_text(_T1)
    return path


def _structure_df():
    """Compute the per-network structure table once (europe realism ladder first,
    then the single-layer regions). Shared by the main and appendix tables so the
    (path-metric) computation is not repeated."""
    from src.evaluate.aggregate import structure_table

    df = structure_table(write=False)
    if df is None or df.empty:
        return None
    df = df.assign(_rk=(df["region"] != "europe").astype(int))
    return df.sort_values(["_rk", "region", "combo"]).reset_index(drop=True)


def _net_name(r) -> str:
    return f"{r['region']}/{r['combo']}".replace("_", r"\_")


def table_structure(df) -> Path:
    """T2 (main text) — the epidemiologically important descriptors only: mean
    degree, the heterogeneity ratio k2/k (which sets the network epidemic
    threshold), degree assortativity, the small-world average path length,
    community modularity, and rho(degree, betweenness) with the anomalous-gateway
    count. The full descriptor set is in the appendix table."""
    body = [
        f"{_net_name(r)} & {int(r['n_nodes'])} & {r['mean_degree']:.1f} & "
        f"{r['k2_over_k']:.1f} & {r['assortativity']:.3f} & "
        f"{r['avg_path_length']:.2f} & {r['modularity']:.3f} & "
        f"{r['spearman_deg_btw']:.3f} & {int(r['n_anomalous'])} \\\\"
        for _, r in df.iterrows()
    ]
    tex = (
        "\\begin{table*}[tp]\n\\centering\n"
        "\\caption{Key structural descriptors per network (topological, no "
        "simulation). $\\langle k\\rangle$ mean degree; "
        "$\\langle k^2\\rangle/\\langle k\\rangle$ the degree heterogeneity "
        "governing the invasion threshold; $r$ degree assortativity; $\\langle\\ell"
        "\\rangle$ mean shortest-path length (small-world); $Q$ community "
        "modularity; $\\rho$ Spearman correlation of degree and betweenness with "
        "the number of anomalous gateways. Full descriptor set in "
        "Table~\\ref{tab:structure-full}.}\n\\label{tab:structure}\n"
        "\\begin{tabular}{l r r r r r r r r}\n\\toprule\n"
        "Network & $n$ & $\\langle k\\rangle$ & "
        "$\\langle k^2\\rangle/\\langle k\\rangle$ & $r$ & $\\langle\\ell\\rangle$ "
        "& $Q$ & $\\rho$ & \\#gw \\\\\n\\midrule\n"
        + "\n".join(body)
        + "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n"
    )
    TEX.mkdir(parents=True, exist_ok=True)
    path = TEX / "T2-structure.tex"
    path.write_text(tex)
    return path


def table_structure_full(df) -> Path:
    """Appendix — the complete descriptor set per network: order/size, density,
    the degree moments, assortativity, clustering, the small-world path length and
    diameter, giant-component fraction, community modularity, the leading
    non-backtracking eigenvalue and its structural percolation threshold
    $T_c=1/\\lambda_{NB}$ (a spectral descriptor of the graph, not a fitted
    threshold of the metapopulation dynamics), and the degree-betweenness
    correlation with the anomalous-gateway count."""
    body = [
        f"{_net_name(r)} & {int(r['n_nodes'])} & {int(r['n_edges'])} & "
        f"{r['density']:.4f} & {r['mean_degree']:.1f} & {r['k2_over_k']:.1f} & "
        f"{r['assortativity']:.3f} & {r['clustering']:.3f} & "
        f"{r['avg_path_length']:.2f} & {int(r['diameter'])} & "
        f"{r['giant_frac']:.3f} & {r['modularity']:.3f} & "
        f"{r['nb_eigenvalue']:.2f} & {r['epi_threshold']:.4f} & "
        f"{r['spearman_deg_btw']:.3f} & {int(r['n_anomalous'])} \\\\"
        for _, r in df.iterrows()
    ]
    tex = (
        "\\begin{table}[ht]\n\\centering\\scriptsize\n\\setlength{\\tabcolsep}{3.5pt}\n"
        "\\caption{Full structural descriptor set per network (topological). "
        "$n$/$m$ nodes/edges; $\\delta$ density; $\\langle k\\rangle$ mean degree; "
        "$\\langle k^2\\rangle/\\langle k\\rangle$ heterogeneity; $r$ assortativity; "
        "$C$ average clustering; $\\langle\\ell\\rangle$/$d$ mean shortest-path "
        "length and diameter (undirected largest component); GC giant-component "
        "fraction; $Q$ Louvain modularity; $\\lambda_{NB}$ leading non-backtracking "
        "eigenvalue and $T_c=1/\\lambda_{NB}$ the structural percolation threshold; "
        "$\\rho$ degree-betweenness correlation; \\#gw anomalous gateways.}\n"
        "\\label{tab:structure-full}\n"
        "\\begin{tabular}{l r r r r r r r r r r r r r r r}\n\\toprule\n"
        "Network & $n$ & $m$ & $\\delta$ & $\\langle k\\rangle$ & "
        "$\\langle k^2\\rangle/\\langle k\\rangle$ & $r$ & $C$ & "
        "$\\langle\\ell\\rangle$ & $d$ & GC & $Q$ & $\\lambda_{NB}$ & $T_c$ & "
        "$\\rho$ & \\#gw \\\\\n\\midrule\n"
        + "\n".join(body)
        + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    TEX.mkdir(parents=True, exist_ok=True)
    path = TEX / "TA-structure-full.tex"
    path.write_text(tex)
    return path


def build_all(echo=print) -> list[Path]:
    made = [table_archetypes()]
    echo(f"  wrote {made[0].relative_to(ROOT)}")
    df = _structure_df()
    if df is None:
        echo("  skip structure tables: no built graphs found")
    else:
        for fn in (table_structure, table_structure_full):
            out = fn(df)
            made.append(out)
            echo(f"  wrote {out.relative_to(ROOT)}")
    return made


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

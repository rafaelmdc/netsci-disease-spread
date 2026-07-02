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
_T1 = r"""\begin{table*}[t]
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
5 & Recurrent, waning immunity   & SEIRS  & seasonal influenza, RSV, norovirus & seasonal influenza \\
\bottomrule
\end{tabular}
\end{table*}
"""


def table_archetypes() -> Path:
    TEX.mkdir(parents=True, exist_ok=True)
    path = TEX / "T1-disease-archetypes.tex"
    path.write_text(_T1)
    return path


def build_all(echo=print) -> list[Path]:
    out = table_archetypes()
    echo(f"  wrote {out.relative_to(ROOT)}")
    return [out]


def _read(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_parquet(path) if path.exists() else None

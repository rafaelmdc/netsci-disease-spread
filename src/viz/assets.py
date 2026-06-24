"""Shared Plotly bundle so every figure isn't a 3.5 MB copy of plotly.js.

`include_plotlyjs="inline"` embeds the whole library in *each* HTML file (≈3.5 MB
× hundreds of runs ≈ gigabytes). `"directory"` is no better here — it drops a
copy into every run folder. Instead we write **one** ``plotly.min.js`` at the
results root and point every figure at it via a relative ``<script src>``; the
files stay fully offline but shrink to just their own data.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.paths import RESULTS, ensure_parent

_BUNDLE = RESULTS / "plotly.min.js"


def plotlyjs_ref(html_path: str | Path) -> str:
    """Ensure the shared bundle exists and return a relative href to it from the
    figure's directory (suitable to pass as ``include_plotlyjs``)."""
    if not _BUNDLE.exists():
        from plotly.offline import get_plotlyjs

        ensure_parent(_BUNDLE)
        _BUNDLE.write_text(get_plotlyjs())
    rel = os.path.relpath(_BUNDLE, Path(html_path).parent)
    return Path(rel).as_posix()  # forward slashes for the HTML href

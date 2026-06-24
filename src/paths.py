"""Canonical filesystem layout for pipeline artifacts.

All artifact dirs (data/, results/) are git-ignored and reproduced by the
pipeline. Output paths are derived from a run's region/layer-combination/label
so the same config always lands in the same place.

**Figures live with their data** (see docs/VISUALIZATION.md): a run's HTML
sits inside its run folder, a network's panels sit in the network folder, and
study-wide outputs sit at the results root. There is no separate ``figures/``
tree — open a results folder and you get its whole story.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
RESULTS = ROOT / "results"


def combo_name(layers: Iterable[str]) -> str:
    """Canonical name for a layer combination, e.g. ['air','land'] -> 'air+land'."""
    return "+".join(sorted(str(layer) for layer in layers))


def raw_dir(layer: str) -> Path:
    return RAW / layer


def processed_graph(region: str, combo: str) -> Path:
    return PROCESSED / region / f"{combo}.graphml"


def results_dir(region: str, combo: str) -> Path:
    return RESULTS / region / combo


def run_dir(region: str, combo: str, label: str) -> Path:
    """One self-contained folder per run, named by its human-readable label."""
    return results_dir(region, combo) / label


def run_json(region: str, combo: str, label: str) -> Path:
    return run_dir(region, combo, label) / "summary.json"


def run_timeseries(region: str, combo: str, label: str) -> Path:
    return run_dir(region, combo, label) / "timeseries.parquet"


def run_node_timeseries(region: str, combo: str, label: str) -> Path:
    """Per-node, per-day infectious counts (+ coords) for geo-animation.
    Written only for runs flagged to record nodes — see runner.run_and_save."""
    return run_dir(region, combo, label) / "node_timeseries.parquet"


def run_figure(region: str, combo: str, label: str, name: str) -> Path:
    """A figure co-located inside one run's folder, e.g. 'curves.html'."""
    return run_dir(region, combo, label) / name


def network_figure(region: str, combo: str, name: str) -> Path:
    """A figure co-located in one network's folder (spans its runs),
    e.g. 'structure.html', 'strategy_panel.html'."""
    return results_dir(region, combo) / name


def results_figure(name: str) -> Path:
    """A study-wide output at the results root, e.g. 'region_spectrum.html'."""
    return RESULTS / name


def ensure_parent(path: Path) -> Path:
    """Make the parent directory of a file path and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: Path) -> Path:
    """Make a directory and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path

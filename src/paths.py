"""Canonical filesystem layout for pipeline artifacts.

All artifact dirs (data/, results/, figures/) are git-ignored and
reproduced by the pipeline. Output paths are derived from a run's
region/layer-combination/run_id so the same config always lands in the
same place.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


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


def figures_dir(region: str, combo: str) -> Path:
    return FIGURES / region / combo


def ensure_parent(path: Path) -> Path:
    """Make the parent directory of a file path and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: Path) -> Path:
    """Make a directory and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path

"""Discover finished runs under results/ for the interactive explorer.

The Dash app browses whatever is on disk: it scans every ``summary.json``,
reads the metadata needed to populate the dropdowns, and notes which artefacts
(region-summed timeseries, per-node history) each run has. Nothing is
re-simulated here — the app only *reads* the pipeline's outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import RunConfig
from src.paths import RESULTS, combo_name


@dataclass(frozen=True)
class RunEntry:
    label: str
    region: str
    combo: str
    model: str
    strategy: str
    coverage: float
    budget: int
    seed: int
    peak: float
    summary_path: Path

    @property
    def run_dir(self) -> Path:
        return self.summary_path.parent

    @property
    def timeseries_path(self) -> Path:
        return self.run_dir / "timeseries.parquet"

    @property
    def node_timeseries_path(self) -> Path:
        return self.run_dir / "node_timeseries.parquet"

    @property
    def has_nodes(self) -> bool:
        return self.node_timeseries_path.exists()

    @property
    def config(self) -> RunConfig:
        """Rebuild the exact RunConfig from the persisted summary (for on-demand
        re-simulation when per-node history is missing)."""
        d = json.loads(self.summary_path.read_text())
        return RunConfig.model_validate(d["config"])


def scan_runs(root: Path = RESULTS) -> list[RunEntry]:
    entries: list[RunEntry] = []
    for path in sorted(root.rglob("summary.json")):
        try:
            d = json.loads(path.read_text())
            cfg, summ = d["config"], d["summary"]
            entries.append(
                RunEntry(
                    label=d.get("label", d.get("run_id", path.parent.name)),
                    region=cfg["network"]["region"],
                    combo=combo_name(list(cfg["network"]["layers"])),
                    model=cfg["model"]["name"],
                    strategy=cfg["strategy"]["name"],
                    coverage=float(cfg["strategy"]["coverage"]),
                    budget=int(cfg["strategy"].get("budget", 0)),
                    seed=int(cfg["sim"]["seed"]),
                    peak=float(summ.get("peak_infected", 0.0)),
                    summary_path=path,
                )
            )
        except (KeyError, json.JSONDecodeError):
            continue  # skip aggregate files (summary.parquet has no .json twin) / partials
    return entries


def runs_frame(root: Path = RESULTS) -> pd.DataFrame:
    """Catalogue as a DataFrame, one row per run (for filtering in the app)."""
    rows = [
        {
            "label": e.label, "region": e.region, "combo": e.combo,
            "network": f"{e.region} / {e.combo}", "model": e.model,
            "strategy": e.strategy, "coverage": e.coverage, "budget": e.budget,
            "seed": e.seed, "peak": e.peak, "has_nodes": e.has_nodes,
        }
        for e in scan_runs(root)
    ]
    return pd.DataFrame(rows)

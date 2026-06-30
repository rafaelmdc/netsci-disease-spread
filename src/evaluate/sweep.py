"""Run an expanded experiment grid, one graph load per network.

Shared by the ``sweep`` CLI (full factorial) and the staged protocol
(src/evaluate/staged.py), so both drive the engine the same way.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from src.config import RunConfig
from src.evaluate.centrality import betweenness
from src.evaluate.runner import run_and_save
from src.experiment import ExperimentConfig
from src.netgen.graph_io import read_graphml
from src.paths import processed_graph

Echo = Callable[[str], None]
OnRun = Callable[[RunConfig, str], None]


def run_experiment(
    exp: ExperimentConfig,
    workers: int = 4,
    maps: bool = False,
    echo: Echo = print,
    on_run: OnRun | None = None,
) -> int:
    """Expand ``exp`` and run every cell, bucketed so each graph loads once.
    ``on_run(cfg, "region/combo")`` fires after each completed run (for live
    progress). Returns the number of runs executed."""
    groups = exp.grouped_by_network()
    total = sum(len(v) for v in groups.values())
    echo(
        f"running {total} configs across {len(groups)} network(s)"
        f"{' (recording per-node maps)' if maps else ''} ..."
    )
    for (region, combo), cfgs in groups.items():
        graph = read_graphml(processed_graph(region, combo))
        betweenness(graph)  # warm the cache once before threads share the graph

        def _one(cfg, g=graph, where=f"{region}/{combo}"):
            run_and_save(cfg, g, record_nodes=maps)
            if on_run is not None:
                on_run(cfg, where)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_one, cfgs))
        echo(f"  {region}/{combo}: {len(cfgs)} runs -> results/{region}/{combo}/")
    return total

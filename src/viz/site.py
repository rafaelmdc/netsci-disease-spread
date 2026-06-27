"""Generate the navigable, co-located results site (docs/VISUALIZATION.md §3).

Three clickable levels, every figure stored beside its data:

  results/index.html                     whole study (cross-region table)
  results/<region>/<combo>/index.html    one network (structure + panel + runs)
  results/<region>/<combo>/<label>/...   one run (curves [+ animated map])

`build_site()` walks the runs already on disk and (re)writes the figures it can
from existing artefacts — it never simulates. Missing inputs (e.g. a run with no
per-node history, or a network whose graph isn't built) are skipped gracefully.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.netgen.graph_io import read_graphml
from src.paths import (
    RESULTS,
    network_figure,
    network_gexf,
    processed_graph,
    results_figure,
    run_figure,
)
from src.viz.catalog import RunEntry, scan_runs
from src.viz.compare_html import strategy_panel_html
from src.viz.curves_html import curves_to_html
from src.viz.spread_html import spread_to_html
from src.viz.structure_html import structure_to_html

_CSS = (
    "<style>body{font:15px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:60rem;"
    "padding:0 1rem;color:#222}a{color:#1f77b4}h1{margin-bottom:.2rem}"
    "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.4rem .6rem;"
    "text-align:left}th{background:#f5f5f5}.nav{color:#888;font-size:.9em}</style>"
)


def _page(title: str, body: str, up: str | None = None) -> str:
    nav = f"<p class='nav'><a href='{up}'>↑ up</a></p>" if up else ""
    return f"<!doctype html><meta charset='utf-8'><title>{title}</title>{_CSS}{nav}{body}"


def _write_run(entry: RunEntry) -> list[str]:
    """Per-run figures + index. Returns the figure names that were written."""
    region, combo, label = entry.region, entry.combo, entry.label
    written: list[str] = []
    ts = pd.read_parquet(entry.timeseries_path)
    curves_to_html(ts, run_figure(region, combo, label, "curves.html"), title=label)
    written.append("curves.html")
    if entry.has_nodes:
        node_ts = pd.read_parquet(entry.node_timeseries_path)
        spread_to_html(node_ts, run_figure(region, combo, label, "spread_geo.html"), title=label)
        written.append("spread_geo.html")

    links = "".join(
        f"<li><a href='{f}'>{_label_for(f)}</a></li>" for f in written
    ) + "<li><a href='../network.html'>interactive network (this graph)</a></li>"
    body = (
        f"<h1>{label}</h1>"
        f"<p>{region} / {combo} · {entry.model.upper()} · {entry.strategy} · "
        f"peak {entry.peak:,.0f}</p><ul>{links}</ul>"
    )
    idx = run_figure(region, combo, label, "index.html")
    idx.write_text(_page(label, body, up="../index.html"))
    return written


def _label_for(fname: str) -> str:
    return {
        "curves.html": "epidemic curves",
        "spread_geo.html": "animated outbreak map ●",
        "structure.html": "degree vs betweenness (anomalous gateways)",
        "strategy_panel.html": "strategy comparison panel",
        "interdiction.html": "air-interdiction (A–D)",
        "network.html": "interactive network",
        "network.gexf": "Gephi file (.gexf, topology)",
    }.get(fname, fname)


def _write_network(region: str, combo: str, entries: list[RunEntry], summary: pd.DataFrame) -> None:
    figures: list[str] = []
    try:
        graph = read_graphml(processed_graph(region, combo))
        structure_to_html(graph, network_figure(region, combo, "structure.html"),
                          title=f"{region} / {combo}")
        figures.append("structure.html")
        from src.viz.gephi import network_gexf as write_network_gexf

        write_network_gexf(graph, network_gexf(region, combo))
        figures.append("network.gexf")  # download for Gephi (desktop)
        try:  # pyvis is optional; the rest of the site shouldn't depend on it
            from src.viz.network_html import network_to_html

            network_to_html(graph, network_figure(region, combo, "network.html"))
            figures.insert(0, "network.html")
        except ImportError:
            pass
    except FileNotFoundError:
        pass

    sl = summary[(summary["region"] == region) & (summary["combo"] == combo)]
    if not sl.empty and {"model", "strategy", "coverage", "peak_infected"} <= set(sl.columns):
        strategy_panel_html(sl, network_figure(region, combo, "strategy_panel.html"),
                            title=f"Strategies — {region} / {combo}")
        figures.append("strategy_panel.html")
    if network_figure(region, combo, "interdiction.html").exists():
        figures.append("interdiction.html")

    fig_links = "".join(f"<li><a href='{f}'>{_label_for(f)}</a></li>" for f in figures)
    rows = "".join(
        f"<tr><td><a href='{e.label}/index.html'>{e.label}</a></td>"
        f"<td>{e.model.upper()}</td><td>{e.strategy}</td>"
        f"<td>{'' if e.strategy == 'control' else f'{e.coverage:.0%}'}</td>"
        f"<td>{e.peak:,.0f}</td><td>{'●' if e.has_nodes else '○'}</td></tr>"
        for e in sorted(entries, key=lambda e: (e.model, e.strategy, e.coverage, e.seed))
    )
    body = (
        f"<h1>{region} / {combo}</h1>"
        f"<h3>Network figures</h3><ul>{fig_links}</ul>"
        f"<h3>Runs ({len(entries)})</h3><table><tr><th>run</th><th>model</th>"
        f"<th>strategy</th><th>coverage</th><th>peak</th><th>map</th></tr>{rows}</table>"
    )
    network_figure(region, combo, "index.html").write_text(
        _page(f"{region}/{combo}", body, up="../../index.html")
    )


def _write_root(groups: dict[tuple[str, str], list[RunEntry]]) -> None:
    spectrum = ""
    struct_path = RESULTS / "structure.parquet"
    if struct_path.exists():
        df = pd.read_parquet(struct_path).sort_values("spearman_deg_btw", ascending=False)
        srows = "".join(
            f"<tr><td>{r['region']}</td><td>{r['spearman_deg_btw']:.3f}</td>"
            f"<td>{int(r['n_anomalous'])}</td></tr>"
            for _, r in df.iterrows()
        )
        spectrum = (
            "<h3>Cross-region centrality spectrum</h3>"
            "<p>Higher ρ ⇒ US-like (degree &amp; betweenness agree); "
            "lower ⇒ worldwide-like (anomalous gateways).</p>"
            "<table><tr><th>region</th><th>ρ(deg,btw)</th><th># anomalous</th></tr>"
            f"{srows}</table>"
        )
    net_rows = "".join(
        f"<tr><td><a href='{region}/{combo}/index.html'>{region} / {combo}</a></td>"
        f"<td>{len(entries)}</td></tr>"
        for (region, combo), entries in sorted(groups.items())
    )
    body = (
        "<h1>Disease-spread results</h1>"
        "<p>Browse interactively with the simulator app "
        "(<code>netsci dashboard</code>), or click through the static pages below.</p>"
        f"{spectrum}"
        "<h3>Networks</h3><table><tr><th>network</th><th>runs</th></tr>"
        f"{net_rows}</table>"
    )
    results_figure("index.html").write_text(_page("results", body))


def build_site() -> dict[str, int]:
    """(Re)build every index + figure from on-disk runs. Returns a small tally."""
    entries = scan_runs()
    summary_path = RESULTS / "summary.parquet"
    summary = pd.read_parquet(summary_path) if summary_path.exists() else pd.DataFrame()

    groups: dict[tuple[str, str], list[RunEntry]] = defaultdict(list)
    for e in entries:
        groups[(e.region, e.combo)].append(e)

    for e in entries:
        _write_run(e)
    for (region, combo), es in groups.items():
        _write_network(region, combo, es, summary)
    _write_root(groups)
    return {"runs": len(entries), "networks": len(groups)}

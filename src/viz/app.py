"""Interactive results explorer — browse every run from one browser tab.

`netsci viz app` launches a Dash server that reads the pipeline's outputs under
results/ (nothing is re-simulated unless you ask): pick a network, model and
strategy, then watch the outbreak animate across the map, inspect the epidemic
curves, and compare strategies / regions — all without regenerating a single
HTML file.

Per-node history (needed for the animated map) is recorded only for some runs;
when it's missing for the selected run, the app offers a one-click
re-simulation that writes it next to the run and refreshes.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, Input, Output, State, callback, dcc, html

from src.evaluate.runner import run_and_save
from src.paths import RESULTS
from src.viz.catalog import RunEntry, runs_frame, scan_runs
from src.viz.compare_html import region_spectrum_figure, strategy_comparison_figure
from src.viz.curves_html import curves_figure
from src.viz.spread_html import spread_figure

_ALL = "— all —"


def _options(values) -> list[dict]:
    return [{"label": _ALL, "value": _ALL}] + [
        {"label": str(v), "value": str(v)} for v in sorted(map(str, set(values)))
    ]


def _filtered(df: pd.DataFrame, network: str, model: str, strategy: str) -> pd.DataFrame:
    if network and network != _ALL:
        df = df[df["network"] == network]
    if model and model != _ALL:
        df = df[df["model"] == model]
    if strategy and strategy != _ALL:
        df = df[df["strategy"] == strategy]
    return df


_SEP = "‖"


def _group_key(row: pd.Series) -> str:
    """Stable id for one configuration *across seeds* (the run dropdown unit)."""
    return _SEP.join(
        [row["region"], row["combo"], row["model"], row["strategy"], str(row["coverage"])]
    )


def _group_label(row: pd.Series) -> str:
    cov = "" if row["strategy"] == "control" else f" · cov {row['coverage']:.0%}"
    return f"{row['network']} · {row['model'].upper()} · {row['strategy']}{cov}"


def _find_run(group_key: str, seed) -> RunEntry | None:
    if not group_key or seed is None:
        return None
    region, combo, model, strategy, cov = group_key.split(_SEP)
    cov, seed = float(cov), int(seed)
    for e in scan_runs():
        if (e.region == region and e.combo == combo and e.model == model
                and e.strategy == strategy and abs(e.coverage - cov) < 1e-9 and e.seed == seed):
            return e
    return None


def _layout() -> dbc.Container:
    df = runs_frame()
    empty = df.empty
    networks = [] if empty else df["network"]
    models = [] if empty else df["model"]
    strategies = [] if empty else df["strategy"]
    return dbc.Container(
        [
            html.H3("Disease-spread results explorer", className="mt-3"),
            html.P(
                "Pick a configuration, then a seed. Runs are deterministic, so the "
                "outbreak map is the run's real dynamics — rendered (and cached) on first "
                "view. ● next to a seed = map already cached.",
                className="text-muted",
            ),
            dbc.Alert(
                "No runs found under results/. Run a sweep first: "
                "`netsci evaluate sweep`.",
                color="warning",
            )
            if empty
            else None,
            dbc.Row(
                [
                    dbc.Col([dbc.Label("Network"),
                             dcc.Dropdown(id="f-network", options=_options(networks),
                                          value=_ALL, clearable=False)], md=4),
                    dbc.Col([dbc.Label("Model"),
                             dcc.Dropdown(id="f-model", options=_options(models),
                                          value=_ALL, clearable=False)], md=3),
                    dbc.Col([dbc.Label("Strategy"),
                             dcc.Dropdown(id="f-strategy", options=_options(strategies),
                                          value=_ALL, clearable=False)], md=3),
                ],
                className="g-2",
            ),
            dbc.Row(
                [
                    dbc.Col([dbc.Label("Run (model · strategy · coverage)"),
                             dcc.Dropdown(id="run", clearable=False)], md=9),
                    dbc.Col([dbc.Label("Seed"),
                             dcc.Dropdown(id="seed", clearable=False)], md=3),
                ],
                className="g-2 mt-1",
            ),
            dbc.Tabs(
                [
                    dbc.Tab(label="Outbreak map", tab_id="map"),
                    dbc.Tab(label="Epidemic curves", tab_id="curves"),
                    dbc.Tab(label="Compare strategies", tab_id="compare"),
                    dbc.Tab(label="Degree vs betweenness gap", tab_id="gap"),
                    dbc.Tab(label="Region spectrum", tab_id="spectrum"),
                ],
                id="tabs", active_tab="map", className="mt-3",
            ),
            dcc.Loading(html.Div(id="content", className="mt-2"), type="default"),
        ],
        fluid=True,
    )


def build_app() -> Dash:
    app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY],
               title="Disease-spread explorer")
    app.layout = _layout

    @callback(
        Output("run", "options"), Output("run", "value"),
        Input("f-network", "value"), Input("f-model", "value"), Input("f-strategy", "value"),
        State("run", "value"),
    )
    def _runs(network, model, strategy, current):
        df = _filtered(runs_frame(), network, model, strategy)
        if df.empty:
            return [], None
        df = df.sort_values(["network", "model", "strategy", "coverage", "seed"])
        df = df.drop_duplicates(subset=["region", "combo", "model", "strategy", "coverage"])
        opts = [{"label": _group_label(r), "value": _group_key(r)} for _, r in df.iterrows()]
        values = {o["value"] for o in opts}
        value = current if current in values else opts[0]["value"]
        return opts, value

    @callback(
        Output("seed", "options"), Output("seed", "value"),
        Input("run", "value"), State("seed", "value"),
    )
    def _seeds(group_key, current):
        if not group_key:
            return [], None
        region, combo, model, strategy, cov = group_key.split(_SEP)
        cov = float(cov)
        df = runs_frame()
        m = ((df["region"] == region) & (df["combo"] == combo) & (df["model"] == model)
             & (df["strategy"] == strategy) & ((df["coverage"] - cov).abs() < 1e-9))
        sub = df[m].sort_values("seed")
        opts = [{"label": f"seed {int(r.seed)}" + (" ●" if r.has_nodes else ""),
                 "value": int(r.seed)} for _, r in sub.iterrows()]
        values = {o["value"] for o in opts}
        value = current if current in values else (opts[0]["value"] if opts else None)
        return opts, value

    @callback(
        Output("content", "children"),
        Input("tabs", "active_tab"), Input("run", "value"), Input("seed", "value"),
    )
    def _content(tab, group_key, seed):
        if tab == "compare":
            return _study_fig(RESULTS / "summary.parquet", strategy_comparison_figure,
                              "No runs aggregated yet.")
        if tab == "gap":
            return _gap_table()
        if tab == "spectrum":
            return _spectrum()
        entry = _find_run(group_key, seed)
        if entry is None:
            return dbc.Alert("Select a run and seed.", color="secondary")
        if tab == "curves":
            ts = pd.read_parquet(entry.timeseries_path)
            return dcc.Graph(figure=curves_figure(ts, title=entry.label), style={"height": "78vh"})
        # map tab — render the run's per-node history (deterministic; cached on first view)
        if not entry.has_nodes:
            run_and_save(entry.config, record_nodes=True)  # materialise this run's map, then cache
        node_ts = pd.read_parquet(entry.node_timeseries_path)
        sub = f"{entry.strategy} · seed {entry.seed} · peak {entry.peak:,.0f}"
        return dcc.Graph(figure=spread_figure(node_ts, title=entry.label, subtitle=sub),
                         style={"height": "80vh"})

    return app


def _study_fig(path, figure_builder, missing_msg: str):
    """Render a study-wide figure from a parquet table, or a hint if absent."""
    if not path.exists():
        return dbc.Alert(missing_msg, color="info")
    return dcc.Graph(figure=figure_builder(pd.read_parquet(path)), style={"height": "78vh"})


def _spectrum():
    """Region spectrum, air-only (the fair cross-region comparison)."""
    path = RESULTS / "structure.parquet"
    if not path.exists():
        return dbc.Alert("No built networks to compare yet.", color="info")
    df = pd.read_parquet(path)
    if "combo" in df.columns:
        df = df[df["combo"] == "air"]  # uniform layer => differences are topology
    if df.empty:
        return dbc.Alert("Need air networks across regions for the spectrum.", color="info")
    return dcc.Graph(figure=region_spectrum_figure(df), style={"height": "78vh"})


def _gap_table():
    """The thesis number as a table: is degree-targeting as good as betweenness?"""
    path = RESULTS / "strategy_gap.parquet"
    if not path.exists():
        return dbc.Alert(
            "No degree/betweenness runs aggregated yet — the gap appears once the "
            "sweep includes both strategies.", color="info")
    df = pd.read_parquet(path).copy()
    df["peak_degree"] = df["peak_degree"].map(lambda v: f"{v:,.0f}")
    df["peak_betweenness"] = df["peak_betweenness"].map(lambda v: f"{v:,.0f}")
    df["gap_abs"] = df["gap_abs"].map(lambda v: f"{v:,.0f}")
    df["gap_rel"] = df["gap_rel"].map(lambda v: f"{v:+.1%}")
    df = df.rename(columns={
        "peak_degree": "peak (degree)", "peak_betweenness": "peak (betweenness)",
        "gap_abs": "gap (people)", "gap_rel": "gap (%)",
    })
    return html.Div([
        html.P("Peak infections under degree- vs betweenness-targeted vaccination "
               "(averaged over seeds). A near-zero gap means the cheap degree strategy "
               "is as good as the expensive betweenness one (US-like); a positive gap "
               "means betweenness contains the outbreak better.", className="text-muted"),
        dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, size="sm"),
    ])


def ensure_tables(rebuild_structure: bool = False) -> None:
    """Build the study-wide tables the app reads, so launching is one command
    end-to-end. ``collect`` is cheap (reads JSONs) and always refreshes;
    ``structure`` recomputes betweenness per network, so it's built only when
    missing (or forced)."""
    from src.evaluate.aggregate import collect, structure_table

    collect(write=True)  # summary.parquet + strategy_gap.parquet
    if rebuild_structure or not (RESULTS / "structure.parquet").exists():
        structure_table(write=True)  # structure.parquet (region spectrum)


def main(host: str = "127.0.0.1", port: int = 8050, debug: bool = False,
         rebuild_structure: bool = False) -> None:
    ensure_tables(rebuild_structure=rebuild_structure)
    build_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()

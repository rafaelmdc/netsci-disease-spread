"""Map the 'new simulation' form onto a validated RunConfig, and discover which
networks are actually built so the form only offers runnable scenarios."""

from __future__ import annotations

from src.config import (
    DISEASE_PRESETS,
    UI_MODELS,
    UI_STRATEGIES,
    GroundBy,
    InterdictionConfig,
    Layer,
    ModelConfig,
    ModelName,
    ModelParams,
    NetworkConfig,
    RunConfig,
    SimConfig,
    StrategyConfig,
    StrategyName,
)
from src.paths import PROCESSED, RESULTS, combo_name, processed_graph, raw_dir

# the canonical file each retrieval produces, used as the "present?" check
_SOURCES = {
    "air": ("OpenFlights (air)", "airports.dat"),
    "geonames": ("GeoNames cities", "cities1000.txt"),
    "water": ("OSM ferries (water)", "ferries_world.json"),
}


def form_options() -> dict:
    """Model/strategy choices + disease presets shared by the run and study forms.

    ``models`` carry a human label (the article disease type); ``presets`` lets the
    form auto-fill the correct literature rates when a model is picked. SQIR and
    KCORE are excluded (see config.UI_MODELS / UI_STRATEGIES)."""
    return {
        "models": [{"value": m.value,
                    "label": f"{m.value.upper()} · {DISEASE_PRESETS[m]['label']}"}
                   for m in UI_MODELS],
        "strategies": [s.value for s in UI_STRATEGIES],
        "presets": {m.value: DISEASE_PRESETS[m]["params"] for m in UI_MODELS},
    }


def data_status() -> dict:
    """Which raw sources are retrieved (+ provenance) and which networks built."""
    sources = []
    for key, (label, filename) in _SOURCES.items():
        d = raw_dir(key)
        present = (d / filename).exists()
        prov = d / "PROVENANCE.txt"
        info = prov.read_text().splitlines()[0] if prov.exists() else ""
        sources.append({"key": key, "label": label, "present": present, "info": info})
    networks = available_networks()
    # has anyone produced runs / rolled them up into the aggregate tables yet?
    has_runs = any(RESULTS.glob("*/*/*/summary.json")) if RESULTS.exists() else False
    aggregates = [
        {"label": "summary.parquet", "present": (RESULTS / "summary.parquet").exists()},
        {"label": "structure.parquet", "present": (RESULTS / "structure.parquet").exists()},
    ]
    return {
        "sources": sources,
        "networks": networks,
        "has_networks": bool(networks),
        "has_runs": has_runs,
        "aggregates": aggregates,
    }


def available_networks() -> dict[str, list[list[str]]]:
    """{region: [[layers], ...]} for every built ``<region>/<combo>.graphml``."""
    out: dict[str, list[list[str]]] = {}
    if not PROCESSED.exists():
        return out
    for region_dir in sorted(p for p in PROCESSED.iterdir() if p.is_dir()):
        combos = [g.stem.split("+") for g in sorted(region_dir.glob("*.graphml"))]
        if combos:
            out[region_dir.name] = combos
    return out


def graph_is_built(region: str, layers: list[str]) -> bool:
    return processed_graph(region, combo_name(layers)).exists()


def _f(form: dict, key: str, default: float) -> float:
    val = form.get(key, "")
    return float(val) if str(val).strip() else default


def _i(form: dict, key: str, default: int) -> int:
    val = form.get(key, "")
    return int(float(val)) if str(val).strip() else default


def _floats(form, key: str, default: list[float]) -> list[float]:
    vals = [float(x) for x in form.getlist(key) if str(x).strip()]
    return vals or default


def _ints(form, key: str, default: list[int]) -> list[int]:
    vals = [int(float(x)) for x in form.getlist(key) if str(x).strip()]
    return vals or default


def build_study_config(form) -> dict:
    """Turn the multi-run form into an experiment-config dict (a small sweep).

    List fields (β, coverage, τ, seed) become sweep axes; checkbox groups
    (models, strategies, transport networks) the others — each ticked network
    combo ("air", "air+land+water", …) becomes its own substrate in the sweep.
    β values are carried as ``beta_scales`` on a base β of 1.0, so each model's β
    ends up exactly the value entered."""
    region = form.get("region", "europe")
    combos = form.getlist("combos") or ["air"]
    networks = [{"region": region, "layers": c.split("+")} for c in combos]
    models_sel = form.getlist("models") or ["sir"]
    strategies = form.getlist("strategies") or ["control"]

    # Each selected disease carries its own literature preset (beta = R0*gamma,
    # etc.), so the study reproduces the paper's per-disease parameterisation
    # instead of applying one generic beta to every model. beta_scales stays as a
    # shared R0-sensitivity multiplier on top (default 1.0 = the preset values).
    models: dict[str, dict] = {
        m: dict(DISEASE_PRESETS[ModelName(m)]["params"]) for m in models_sel
    }

    cfg: dict = {
        "networks": networks,
        "models": models,
        "strategies": strategies,
        "budgets": [int(form.get("budget", 15))],
        "coverages": _floats(form, "coverages", [0.75]),
        "efficacies": [float(form.get("efficacy", 0.85))],
        "beta_scales": _floats(form, "beta_scales", [1.0]),
        "taus": _floats(form, "taus", [0.0002]),
        "horizons": [int(form.get("horizon", 1460))],
        "seeds": _ints(form, "seeds", [0]),
        "seed_size": int(form.get("seed_size", 2500)),
    }
    all_layers = {layer for net in networks for layer in net["layers"]}
    if all_layers & {"land", "water"}:
        cfg["tau_by_layer"] = {"air": 0.0002, "land": 0.3, "water": 0.0005}

    # Staged ('greedy with re-check') protocol: the selected networks become the
    # realism ladder (rungs); the largest is the flagship for the re-check.
    if form.get("mode") == "staged":
        rungs = [net["layers"] for net in networks]
        cfg["protocol"] = {
            "mode": "staged",
            "ladder_region": region,
            "rungs": rungs,
            "anchor_disease": form.get("anchor") or models_sel[0],
            "flagship": max(rungs, key=len),
            "rank_by": "peak_infected",
            # Stage 4 dose-response: sweep the winning strategy's budget on the
            # flagship (matches experiment.yaml, feeds the dose-response figure).
            "budget_grid": _ints(form, "budget_grid", [5, 15, 30, 60, 120, 200]),
        }
    return cfg


def _interdiction(form) -> InterdictionConfig | None:
    """Edge-level intervention from the form: ticked layers to close + an
    optional top-k airport grounding. None when nothing is selected."""
    close = [Layer(name) for name in ("air", "land", "water") if form.get(f"close_{name}")]
    k = _i(form, "ground_k", 0)
    if not close and k <= 0:
        return None
    return InterdictionConfig(
        close_layers=close, ground_top_k=k, ground_by=GroundBy(form.get("ground_by", "degree"))
    )


def parse_run_form(form: dict) -> RunConfig:
    """Build a RunConfig from the submitted form (pydantic validates it)."""
    region = form.get("region", "europe")
    layers = form.getlist("layers") if hasattr(form, "getlist") else form.get("layers", ["air"])
    if isinstance(layers, str):
        layers = [layers]
    if not layers:
        layers = ["air"]

    model_name = ModelName(form.get("model", "sir"))
    # Start from the disease's literature preset (correct rates for every model,
    # including SEIQRD/SEIRS), then apply any explicit form overrides.
    params = dict(DISEASE_PRESETS[model_name]["params"])
    for key in list(params):
        val = form.get(key, "")
        if str(val).strip():
            params[key] = float(val)

    tau_air = _f(form, "tau", 0.0002)

    return RunConfig(
        network=NetworkConfig(region=region, layers=[Layer(x) for x in layers]),
        model=ModelConfig(name=model_name, params=ModelParams(**params)),
        strategy=StrategyConfig(
            name=StrategyName(form.get("strategy", "control")),
            budget=_i(form, "budget", 15),
            coverage=_f(form, "coverage", 0.75),
            efficacy=_f(form, "efficacy", 0.85),
        ),
        sim=SimConfig(
            horizon=_i(form, "horizon", 75),
            tau=tau_air,
            seed_size=_i(form, "seed_size", 2500),
            seed=_i(form, "seed", 0),
            steps_per_day=_i(form, "steps_per_day", 1),
        ),
        interdiction=_interdiction(form),
    )

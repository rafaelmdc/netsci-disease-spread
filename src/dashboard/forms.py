"""Map the 'new simulation' form onto a validated RunConfig, and discover which
networks are actually built so the form only offers runnable scenarios."""

from __future__ import annotations

from src.config import (
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

    gamma = float(form.get("gamma", 0.12))
    sigma = float(form.get("sigma", 0.2))
    kappa = float(form.get("kappa", 0.15))
    gamma_q = float(form.get("gamma_q", 0.1))

    models: dict[str, dict] = {}
    for m in models_sel:
        params = {"beta": 1.0, "gamma": gamma}  # β swept via beta_scales below
        if m in ("seir", "sqir"):
            params["sigma"] = sigma
        if m == "sqir":
            params["kappa"] = kappa
            params["gamma_q"] = gamma_q
        models[m] = params

    cfg: dict = {
        "networks": networks,
        "models": models,
        "strategies": strategies,
        "budgets": [int(form.get("budget", 15))],
        "coverages": _floats(form, "coverages", [0.75]),
        "efficacies": [float(form.get("efficacy", 0.85))],
        "beta_scales": _floats(form, "betas", [0.32]),
        "taus": _floats(form, "taus", [0.0002]),
        "horizons": [int(form.get("horizon", 210))],
        "seeds": _ints(form, "seeds", [0]),
        "seed_size": int(form.get("seed_size", 2500)),
    }
    all_layers = {layer for net in networks for layer in net["layers"]}
    if all_layers & {"land", "water"}:
        cfg["tau_by_layer"] = {"air": 0.0002, "land": 0.3, "water": 0.0005}
    return cfg


def parse_run_form(form: dict) -> RunConfig:
    """Build a RunConfig from the submitted form (pydantic validates it)."""
    region = form.get("region", "europe")
    layers = form.getlist("layers") if hasattr(form, "getlist") else form.get("layers", ["air"])
    if isinstance(layers, str):
        layers = [layers]
    if not layers:
        layers = ["air"]

    model_name = ModelName(form.get("model", "sir"))
    params: dict = {"beta": _f(form, "beta", 0.4), "gamma": _f(form, "gamma", 0.1)}
    if model_name in (ModelName.SEIR, ModelName.SQIR):
        params["sigma"] = _f(form, "sigma", 0.2)
    if model_name == ModelName.SQIR:
        params["kappa"] = _f(form, "kappa", 0.15)
        params["gamma_q"] = _f(form, "gamma_q", 0.08)

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
    )

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
from src.paths import PROCESSED, combo_name, processed_graph


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

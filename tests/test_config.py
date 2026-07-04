import pytest
from pydantic import ValidationError

from src.config import ModelConfig, ModelName, ModelParams, RunConfig, SimConfig


def _base_run(**sim_kwargs) -> RunConfig:
    return RunConfig(
        model=ModelConfig(name=ModelName.SIR, params=ModelParams(beta=0.3, gamma=0.1)),
        sim=SimConfig(**sim_kwargs),
    )


def test_run_id_is_deterministic():
    assert _base_run(seed=0).run_id == _base_run(seed=0).run_id


def test_run_id_changes_with_seed():
    assert _base_run(seed=0).run_id != _base_run(seed=1).run_id


def test_seir_requires_sigma():
    with pytest.raises(ValidationError):
        ModelConfig(name=ModelName.SEIR, params=ModelParams(beta=0.3, gamma=0.1))


def test_sqir_requires_kappa_and_gamma_q():
    with pytest.raises(ValidationError):
        ModelConfig(name=ModelName.SQIR, params=ModelParams(beta=0.3, gamma=0.1))


def test_disease_presets_match_experiment_yaml():
    """The app forms and the sweep must share one disease parameterisation:
    config.DISEASE_PRESETS is the canonical copy; experiment.yaml must match it."""
    import yaml

    from src.config import DISEASE_PRESETS
    from src.paths import ROOT

    yaml_models = yaml.safe_load((ROOT / "experiment.yaml").read_text())["models"]
    preset_models = {m.value: p["params"] for m, p in DISEASE_PRESETS.items()}
    assert yaml_models == preset_models


def test_disease_presets_build_valid_run_configs():
    """Every UI disease preset must produce a valid RunConfig — regression for the
    forms that silently omitted SEIQRD/SEIRS rates and failed validation."""
    from src.config import DISEASE_PRESETS, UI_MODELS

    for model in UI_MODELS:
        params = ModelParams(**DISEASE_PRESETS[model]["params"])
        ModelConfig(name=model, params=params)  # raises if required rates are missing

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

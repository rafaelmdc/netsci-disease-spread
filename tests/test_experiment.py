from src.config import Layer, ModelName, ModelParams, StrategyName
from src.experiment import ExperimentConfig


def _exp(**kw):
    base = dict(
        regions=["europe"],
        layer_sets=[[Layer.AIR]],
        models={ModelName.SIR: ModelParams(beta=0.3, gamma=0.1)},
        strategies=[StrategyName.CONTROL, StrategyName.DEGREE],
        budgets=[15],
        coverages=[0.75],
        efficacies=[0.85],
        seeds=[0, 1],
    )
    base.update(kw)
    return ExperimentConfig(**base)


def test_expand_counts():
    # (control + degree) x 1 model x 2 seeds = 4
    assert len(_exp().expand()) == 4


def test_control_is_emitted_once_per_coverage():
    # control ignores coverage, so two coverages still yield one control run
    exp = _exp(strategies=[StrategyName.CONTROL], coverages=[0.01, 0.75], seeds=[0])
    assert len(exp.expand()) == 1


def test_multiple_regions_group_separately():
    exp = _exp(regions=["europe", "asia"], strategies=[StrategyName.CONTROL], seeds=[0])
    groups = exp.grouped_by_network()
    assert set(groups.keys()) == {("europe", "air"), ("asia", "air")}


def test_beta_scale_changes_runs():
    one = _exp(strategies=[StrategyName.CONTROL], seeds=[0])
    two = _exp(strategies=[StrategyName.CONTROL], seeds=[0], beta_scales=[1.0, 2.0])
    assert len(two.expand()) == 2 * len(one.expand())

"""Dashboard pure logic: form → RunConfig mapping and the SQLite job ledger."""

from src.config import ModelName, StrategyName


def test_parse_run_form_sir():
    from src.dashboard.forms import parse_run_form

    cfg = parse_run_form({
        "region": "europe", "layers": ["air", "water"], "model": "sir",
        "beta": "0.5", "gamma": "0.2", "strategy": "betweenness",
        "budget": "20", "coverage": "0.6", "efficacy": "0.9",
        "horizon": "40", "tau": "0.001", "seed_size": "100", "seed": "3",
        "steps_per_day": "2",
    })
    assert cfg.network.region == "europe"
    assert [layer.value for layer in cfg.network.layers] == ["air", "water"]
    assert cfg.model.name == ModelName.SIR
    assert cfg.model.params.beta == 0.5 and cfg.model.params.sigma is None
    assert cfg.strategy.name == StrategyName.BETWEENNESS and cfg.strategy.budget == 20
    assert cfg.sim.horizon == 40 and cfg.sim.seed == 3 and cfg.sim.steps_per_day == 2


def test_parse_run_form_seir_includes_sigma():
    from src.dashboard.forms import parse_run_form

    cfg = parse_run_form({"region": "europe", "layers": ["air"], "model": "seir",
                          "beta": "0.4", "gamma": "0.1", "sigma": "0.25"})
    assert cfg.model.name == ModelName.SEIR
    assert cfg.model.params.sigma == 0.25


def test_parse_run_form_interdiction():
    from src.config import GroundBy, Layer
    from src.dashboard.forms import parse_run_form

    cfg = parse_run_form({
        "region": "europe", "layers": ["air"], "model": "sir", "beta": "0.4", "gamma": "0.1",
        "close_water": "on", "ground_k": "10", "ground_by": "betweenness",
    })
    ic = cfg.interdiction
    assert ic is not None
    assert ic.close_layers == [Layer.WATER]
    assert ic.ground_top_k == 10 and ic.ground_by is GroundBy.BETWEENNESS


def test_parse_run_form_no_interdiction_by_default():
    from src.dashboard.forms import parse_run_form

    cfg = parse_run_form({"region": "europe", "layers": ["air"], "model": "sir",
                          "beta": "0.4", "gamma": "0.1"})
    assert cfg.interdiction is None


def test_job_ledger_lifecycle(tmp_path, monkeypatch):
    from src.dashboard import jobs

    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "jobs.db")
    jobs.init_db()

    jid = jobs.create_job("simulate", "europe/air · SIR", config_json="{}")
    assert jobs.get_job(jid)["status"] == "queued"

    jobs.mark_running(jid)
    assert jobs.get_job(jid)["status"] == "running"

    # a crash leaves it 'running'; recovery flips it to 'interrupted'
    assert jobs.recover_stale() == 1
    assert jobs.get_job(jid)["status"] == "interrupted"

    jobs.mark_done(jid, "europe", "air", "sir_control_seed0_abc123")
    done = jobs.get_job(jid)
    assert done["status"] == "done" and done["label"] == "sir_control_seed0_abc123"
    assert jobs.list_jobs()[0]["id"] == jid

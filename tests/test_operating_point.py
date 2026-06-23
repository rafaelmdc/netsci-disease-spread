from src.config import ModelName
from src.evaluate.operating_point import recommend, scan_tau
from src.netgen.toy import build_toy_graph


def test_scan_tau_shape():
    g = build_toy_graph()
    rows = scan_tau(g, ModelName.SIR, taus=[0.0005, 0.002], horizon=120, region="toy")
    assert len(rows) == 2
    assert set(rows[0]) == {"tau", "attack_rate", "peak_day", "peak_reached", "informative"}


def test_higher_tau_peaks_no_later():
    g = build_toy_graph()
    rows = scan_tau(g, ModelName.SIR, taus=[0.0005, 0.005], horizon=200, region="toy")
    assert rows[1]["peak_day"] <= rows[0]["peak_day"]


def test_recommend_returns_informative_or_none():
    g = build_toy_graph()
    rows = scan_tau(g, ModelName.SIR, taus=[0.001, 0.005], horizon=200, region="toy")
    best = recommend(rows)
    assert best is None or best["informative"]

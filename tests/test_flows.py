"""Radiation mobility-model tests."""

import numpy as np

from src.config import Layer
from src.netgen.flows import haversine_km, radiation_flows, top_k_edges
from src.netgen.layers import LAYER_REGISTRY


def test_haversine_known_distance():
    # London (51.5, -0.1) to Paris (48.9, 2.4) is ~340 km
    d = haversine_km(np.array([51.5, 48.9]), np.array([-0.1, 2.4]))
    assert 300 < d[0, 1] < 380
    assert d[0, 0] == 0.0


def test_radiation_flux_nonnegative_zero_diagonal():
    pop = np.array([1e6, 5e5, 2e5, 8e5])
    lat = np.array([51.5, 48.9, 41.9, 52.5])
    lon = np.array([-0.1, 2.4, 12.5, 13.4])
    flux = radiation_flows(pop, lat, lon)
    assert (flux >= 0).all()
    assert np.allclose(np.diag(flux), 0.0)


def test_top_k_edges_limits_out_degree():
    flux = np.array([[0, 3, 1, 2], [1, 0, 5, 2], [0, 0, 0, 0], [4, 1, 2, 0]], dtype=float)
    edges = top_k_edges(flux, k=2)
    out_degree = {}
    for i, _, _ in edges:
        out_degree[i] = out_degree.get(i, 0) + 1
    assert all(v <= 2 for v in out_degree.values())


def test_land_and_water_layers_registered():
    assert Layer.LAND in LAYER_REGISTRY
    assert Layer.WATER in LAYER_REGISTRY

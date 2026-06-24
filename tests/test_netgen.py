"""Region filtering and layer-registry tests (no downloaded data required)."""

import numpy as np
import pandas as pd
import pytest

from src.config import Layer
from src.netgen.layers import LAYER_REGISTRY
from src.netgen.places import resolve_served_cities, snap
from src.netgen.regions import in_region, tz_continent


def test_tz_continent():
    assert tz_continent("Europe/Paris") == "Europe"
    assert tz_continent("America/New_York") == "America"
    assert tz_continent("\\N") is None
    assert tz_continent(None) is None


def test_in_region_europe():
    assert in_region("Europe/Lisbon", "europe")
    assert not in_region("Asia/Tokyo", "europe")


def test_in_region_oceania_covers_australia_and_pacific():
    assert in_region("Australia/Sydney", "oceania")
    assert in_region("Pacific/Auckland", "oceania")


def test_world_accepts_any_valid_tz():
    assert in_region("Africa/Cairo", "world")
    assert not in_region("\\N", "world")


def test_unknown_region_raises():
    with pytest.raises(ValueError):
        in_region("Europe/Paris", "narnia")


def test_air_layer_is_registered():
    assert Layer.AIR in LAYER_REGISTRY


def _toy_cities() -> pd.DataFrame:
    # a metro and the small village its airport physically sits in, ~20 km apart
    return pd.DataFrame(
        {
            "city_id": ["metro", "village", "faraway"],
            "name": ["Metro", "Village", "Faraway"],
            "alts": ["Metropolis", "", ""],  # exonym alias for the metro
            "lat": [51.51, 51.47, 53.50],  # metro & village near; faraway ~250 km
            "lon": [-0.13, -0.46, -0.46],
            "population": [9_000_000, 60_000, 5_000_000],
        }
    )


def test_snap_catchment_picks_served_metro_not_nearest_village():
    """An airport in a village near a metropolis maps to the metro (gravity
    catchment basin), not to the nearest small town it physically sits in."""
    cities = _toy_cities()
    # point sitting right on the village
    [cid] = snap(np.array([51.47]), np.array([-0.46]), cities)
    assert cid == "metro"


def test_snap_returns_none_outside_catchment_radius():
    cities = _toy_cities()
    # mid-Atlantic: no city within the 60 km basin
    [cid] = snap(np.array([45.0]), np.array([-30.0]), cities)
    assert cid is None


def test_snap_does_not_over_pull_a_distant_bigger_city():
    """A rural airport keeps its own nearby town: a bigger city beyond the
    catchment radius must not absorb it."""
    cities = _toy_cities()
    # sit on 'faraway' (>60 km from metro/village) -> stays local
    [cid] = snap(np.array([53.50]), np.array([-0.46]), cities)
    assert cid == "faraway"


def test_resolve_uses_curated_name_over_geometry():
    """The authoritative route wins: an airport whose served city is named
    'Village' maps to Village even though gravity would pull it to the metro."""
    cities = _toy_cities()
    [cid] = resolve_served_cities(["Village"], np.array([51.47]), np.array([-0.46]), cities)
    assert cid == "village"


def test_resolve_matches_exonym_alternate_name():
    """A curated name given as an exonym resolves via the alternate-name list."""
    cities = _toy_cities()
    [cid] = resolve_served_cities(["Metropolis"], np.array([51.51]), np.array([-0.13]), cities)
    assert cid == "metro"


def test_resolve_falls_back_to_gravity_for_unknown_name():
    """An unresolvable served-city name (not in GeoNames) falls back to the
    gravity catchment basin."""
    cities = _toy_cities()
    [cid] = resolve_served_cities(["Nowheresville"], np.array([51.47]), np.array([-0.46]), cities)
    assert cid == "metro"  # gravity basin from the village location


def test_resolve_rejects_far_same_name_city():
    """A same-name city far from the airport is rejected (we don't snap London,
    France's airport to London, UK); falls back to geometry instead."""
    cities = _toy_cities()
    # served city 'Faraway' but airport sits at the metro -> 250 km name hit is
    # rejected, gravity assigns the local metro.
    [cid] = resolve_served_cities(["Faraway"], np.array([51.51]), np.array([-0.13]), cities)
    assert cid == "metro"

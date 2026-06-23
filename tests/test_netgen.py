"""Region filtering and layer-registry tests (no downloaded data required)."""

import pytest

from src.config import Layer
from src.netgen.layers import LAYER_REGISTRY
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

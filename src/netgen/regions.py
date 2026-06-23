"""Region filtering.

We classify a place by the *continent prefix of its IANA timezone* (e.g.
``Europe/Paris`` -> Europe). This is built into the OpenFlights data, needs
no extra country->continent table, and applies uniformly to every layer and
region — which is exactly the consistency the cross-region comparison
requires (see docs/METHODOLOGY.md).
"""

from __future__ import annotations

# region name -> set of acceptable timezone continent prefixes
REGION_TZ_PREFIXES: dict[str, set[str]] = {
    "europe": {"Europe"},
    "asia": {"Asia"},
    "africa": {"Africa"},
    "americas": {"America"},
    "oceania": {"Australia", "Pacific"},
}

ALL_REGIONS = (*REGION_TZ_PREFIXES.keys(), "world")


def tz_continent(tz: str | float | None) -> str | None:
    """Continent prefix of an IANA tz string, or None."""
    if not isinstance(tz, str) or "/" not in tz:
        return None
    return tz.split("/", 1)[0]


def in_region(tz: str | float | None, region: str) -> bool:
    if region == "world":
        return tz_continent(tz) is not None
    prefixes = REGION_TZ_PREFIXES.get(region)
    if prefixes is None:
        raise ValueError(f"unknown region {region!r}; choose from {ALL_REGIONS}")
    return tz_continent(tz) in prefixes

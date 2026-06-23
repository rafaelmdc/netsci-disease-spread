"""Canonical city node set from GeoNames, plus point->city snapping.

Cities (real name, coordinates and population) are the substrate every layer
attaches to: airports snap to their nearest city, ferry terminals snap to
their nearest city, and ground mobility is modelled between cities. This is
what makes the multilayer network correct — layers share real city nodes
rather than hanging off airports.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from src.netgen.flows import haversine_point
from src.netgen.regions import in_region
from src.paths import raw_dir

# GeoNames cities15000.txt columns we use (tab-separated, 19 columns total)
_COLS = {0: "city_id", 1: "name", 4: "lat", 5: "lon", 8: "country", 14: "population", 17: "tz"}


@lru_cache(maxsize=1)
def _all_cities() -> pd.DataFrame:
    df = pd.read_csv(
        raw_dir("geonames") / "cities15000.txt",
        sep="\t",
        header=None,
        usecols=list(_COLS),
        names=[_COLS[i] for i in sorted(_COLS)],
        dtype={"city_id": str, "name": str, "country": str, "tz": str},
    )
    return df


def region_cities(region: str, top_n: int | None = None) -> pd.DataFrame:
    """Cities whose timezone places them in `region`, largest first.
    `top_n` caps the node set (keeps runs tractable for dense regions)."""
    df = _all_cities()
    df = df[df["tz"].map(lambda tz: in_region(tz, region))]
    df = df.sort_values("population", ascending=False).reset_index(drop=True)
    if top_n is not None:
        df = df.head(top_n).reset_index(drop=True)
    return df


def snap(
    plat: np.ndarray, plon: np.ndarray, cities: pd.DataFrame, max_km: float
) -> list[str | None]:
    """Nearest city_id for each (lat, lon) point, or None if beyond max_km."""
    clat = cities["lat"].to_numpy()
    clon = cities["lon"].to_numpy()
    ids = cities["city_id"].to_numpy()
    out: list[str | None] = []
    for la, lo in zip(plat, plon, strict=True):
        d = haversine_point(float(la), float(lo), clat, clon)
        j = int(d.argmin())
        out.append(str(ids[j]) if d[j] <= max_km else None)
    return out

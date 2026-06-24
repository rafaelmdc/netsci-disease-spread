"""Canonical city node set from GeoNames, plus point->city assignment.

Cities (real name, coordinates and population) are the substrate every layer
attaches to: airports and ferry terminals are assigned to the city they
*serve*, and ground mobility is modelled between cities. This is what makes
the multilayer network correct — layers share real city nodes rather than
hanging off airports.

Two assignment routes, in order of authority:

1. **Named served-city (authoritative).** OpenFlights records, per airport, a
   human-curated served *city* ("London" for all five London airports). We
   resolve that name to a GeoNames node (matching name + multilingual
   alternate names, disambiguating same-name cities by proximity). This is
   curated ground truth, not inference, and covers ~93% of air *traffic*.
2. **Gravity catchment basin (fallback / label-less layers).** When no served
   city is given (OSM ferry terminals) or the curated name doesn't resolve, we
   fall back to geometry: within a catchment radius pick the city maximising
   population / distance (Heathrow -> London, not the village it sits in) —
   GLEAM's airport-basin idea (Balcan & Vespignani 2009). Nearest-city snapping,
   by contrast, fragments and mislabels metro hubs.

The base node set is GeoNames cities1000 (places >1000 pop, plus admin seats),
so small towns and islands most airports/ferries serve have a real node. The
few airports whose served place is below even that floor keep their own node
(``apt:<IATA>``) in netgen, so no route is ever dropped.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

import numpy as np
import pandas as pd

from src.netgen.flows import haversine_point
from src.netgen.regions import in_region
from src.paths import raw_dir

# GeoNames cities1000.txt columns we use (tab-separated, 19 columns total).
# Col 3 is the comma-separated multilingual alternate-name list (exonyms like
# "Cologne"/"Kiev"/"Turin"), which lets us resolve OpenFlights' English city
# names to the native-named GeoNames node.
_COLS = {
    0: "city_id", 1: "name", 3: "alts", 4: "lat", 5: "lon",
    8: "country", 14: "population", 17: "tz",
}


def _norm(s: object) -> str:
    """Accent/case-fold a place name for matching ('Köln' -> 'koln')."""
    if not isinstance(s, str):
        return ""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


@lru_cache(maxsize=1)
def _all_cities() -> pd.DataFrame:
    df = pd.read_csv(
        raw_dir("geonames") / "cities1000.txt",
        sep="\t",
        header=None,
        usecols=list(_COLS),
        names=[_COLS[i] for i in sorted(_COLS)],
        dtype={"city_id": str, "name": str, "alts": str, "country": str, "tz": str},
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


# Gravity-catchment parameters for the *fallback* route (and ferries).
# Chosen by validation, not "just because" — scripts/validate_snap.py scores
# the geometry-only rule against OpenFlights' independent served-city labels
# (traffic-weighted): gravity agrees ~84% vs ~44% for nearest-city, on a broad
# plateau over R=60–120 km (<1pp spread). R=60 is the empirical peak and the
# tightest basin that still aggregates multi-airport metros, so it minimises
# over-pull. The 10 km floor means that within one metro's reach distance stops
# deciding and population (which city it serves) does. The authoritative route
# (resolve_served_cities) supersedes this for ~93% of air traffic.
_CATCHMENT_KM = 60.0
_DIST_FLOOR_KM = 10.0


def snap(
    plat: np.ndarray,
    plon: np.ndarray,
    cities: pd.DataFrame,
    max_km: float = _CATCHMENT_KM,
    d_floor: float = _DIST_FLOOR_KM,
) -> list[str | None]:
    """Assign each (lat, lon) point to the city it most plausibly *serves*.

    Gravity catchment: among cities within ``max_km``, pick the one maximising
    ``population / max(distance, d_floor)`` — so a major airport maps to the
    metropolis in its basin rather than the village it physically sits in, while
    a rural terminal still maps to its nearest small town. Returns the city_id,
    or ``None`` if no city lies within ``max_km``.
    """
    clat = cities["lat"].to_numpy()
    clon = cities["lon"].to_numpy()
    cpop = cities["population"].to_numpy(dtype=float)
    ids = cities["city_id"].to_numpy()
    out: list[str | None] = []
    for la, lo in zip(plat, plon, strict=True):
        d = haversine_point(float(la), float(lo), clat, clon)
        within = d <= max_km
        if not within.any():
            out.append(None)
            continue
        score = np.where(within, cpop / np.maximum(d, d_floor), -np.inf)
        out.append(str(ids[int(score.argmax())]))
    return out


# A curated name resolving to a node >100 km from its airport is almost
# certainly a same-name city elsewhere (Villafranca in Lunigiana 143 km from
# Verona's airport), not the served one — reject it and let gravity catchment
# pick the actual nearby metro. 100 km still admits genuine far-sited airports
# (Stockholm-Skavsta, 89 km). Validated in scripts/validate_snap.py.
_RESOLVE_MAX_KM = 100.0


def _name_index(cities: pd.DataFrame) -> dict[str, list[int]]:
    """Map every normalised name/alternate-name to the city row(s) bearing it."""
    idx: dict[str, list[int]] = {}
    for row, (name, alts) in enumerate(zip(cities["name"], cities["alts"], strict=True)):
        keys = {_norm(name)}
        if isinstance(alts, str):
            keys |= {_norm(x) for x in alts.split(",")}
        for k in keys:
            if k:
                idx.setdefault(k, []).append(row)
    return idx


def resolve_served_cities(
    names: list[str],
    plat: np.ndarray,
    plon: np.ndarray,
    cities: pd.DataFrame,
    max_km: float = _CATCHMENT_KM,
) -> list[str | None]:
    """Assign each (served-city *name*, lat, lon) to a GeoNames city_id.

    Authoritative route first: match the curated name against city names +
    alternate names. Among matches within ``_RESOLVE_MAX_KM`` we pick the one
    with the highest gravity score ``population / max(distance, floor)`` — the
    same basin logic as :func:`snap`. That favours the principal city over an
    administrative sub-entry when they're co-located ("London" -> London 8.9M,
    not the tiny "City of London" next door) yet still prefers a *nearby*
    same-name town over a more populous one far away ("Villafranca" -> the one
    by Verona, not Villafranca in Lunigiana 140 km off). Where the name doesn't
    resolve at all, fall back to the gravity catchment :func:`snap`. Returns
    ``None`` only if both routes fail.
    """
    idx = _name_index(cities)
    clat = cities["lat"].to_numpy()
    clon = cities["lon"].to_numpy()
    cpop = cities["population"].to_numpy(dtype=float)
    ids = cities["city_id"].to_numpy()
    fallback = snap(plat, plon, cities, max_km)
    out: list[str | None] = []
    for name, la, lo, fb in zip(names, plat, plon, fallback, strict=True):
        rows = np.array(idx.get(_norm(name), []), dtype=int)
        if rows.size:
            d = haversine_point(float(la), float(lo), clat[rows], clon[rows])
            mask = d <= _RESOLVE_MAX_KM
            if mask.any():
                near, dn = rows[mask], d[mask]
                score = cpop[near] / np.maximum(dn, _DIST_FLOOR_KM)
                out.append(str(ids[near[int(score.argmax())]]))
                continue
        out.append(fb)  # gravity-catchment fallback (may itself be None)
    return out

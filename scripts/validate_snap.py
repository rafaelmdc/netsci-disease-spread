"""Validate how airports are assigned to city nodes.

The air layer assigns each airport to its city by OpenFlights' **curated
served-city label**, resolved to a GeoNames node, with a gravity-catchment
*fallback* only when the label can't be resolved (region-named airports, or
towns below GeoNames' 15k cutoff). See ``src/netgen/places.py``.

Validating the curated-label route against OpenFlights' own labels would be
circular, so this script reports the checks that *are* meaningful:

1. **Coverage** — what share of airports (and of traffic) is assigned by the
   authoritative name vs the gravity fallback vs dropped entirely.
2. **Geometric sanity** — distance from each airport to its assigned city;
   anything far is flagged for inspection (an airport should sit near the city
   it serves). This is what catches a bad assignment without circularity.
3. **Hub aggregation** — multi-airport metros must collapse onto one node
   (all five London airports -> London), the property nearest-city snapping
   destroyed.

Run:  ``uv run python scripts/validate_snap.py [region]``  (default: europe)
"""

from __future__ import annotations

import sys
from collections import Counter

import numpy as np
import pandas as pd

from src.netgen.flows import haversine_point
from src.netgen.places import _name_index, _norm, region_cities, resolve_served_cities

_AIRPORT_COLS = [
    "airport_id", "name", "city", "country", "iata", "icao",
    "lat", "lon", "alt", "tz_offset", "dst", "tz", "type", "source",
]
_ROUTE_COLS = [
    "airline", "airline_id", "src", "src_id", "dst", "dst_id",
    "codeshare", "stops", "equipment",
]
_FAR_KM = 75.0  # assignment distance beyond which we flag for inspection


def main(region: str = "europe") -> None:
    from src.netgen.regions import in_region
    from src.paths import raw_dir

    air = raw_dir("air")
    ap = pd.read_csv(air / "airports.dat", header=None, names=_AIRPORT_COLS, na_values="\\N")
    ap = ap[ap["iata"].notna() & ap["tz"].map(lambda t: in_region(t, region))]
    routes = pd.read_csv(air / "routes.dat", header=None, names=_ROUTE_COLS, na_values="\\N")
    routes = routes[routes["stops"] == 0]
    ap = ap.assign(traffic=ap["iata"].map(routes.groupby("src").size()).fillna(0).astype(int))

    cities = region_cities(region)
    byid = cities.set_index("city_id")
    lat, lon = ap["lat"].to_numpy(), ap["lon"].to_numpy()
    assigned = resolve_served_cities(ap["city"].tolist(), lat, lon, cities)

    # a curated name resolved iff the OpenFlights city is a known GeoNames
    # name/alternate-name — the exact condition resolve_served_cities uses.
    resolvable = set(_name_index(cities))

    n = len(ap)
    by_name = by_fallback = dropped = 0
    tw = tw_dropped = 0.0
    tw_named = 0.0
    far_rows = []
    metro_count: Counter[str] = Counter()
    for (_, r), cid in zip(ap.iterrows(), assigned, strict=True):
        w = float(r["traffic"])
        tw += w
        if cid is None:
            dropped += 1  # no real city in the basin -> dropped (no proxy population)
            tw_dropped += w
            continue
        metro_count[cid] += 1
        if _norm(r["city"]) in resolvable:
            by_name += 1
            tw_named += w
        else:
            by_fallback += 1
        served = byid.loc[cid]
        d = haversine_point(float(r["lat"]), float(r["lon"]),
                            np.array([served["lat"]]), np.array([served["lon"]]))[0]
        if d > _FAR_KM:
            far_rows.append((int(r["traffic"]), r["iata"], r["city"], served["name"], d))

    print(f"region={region}   airports={n}\n")
    print("1. Coverage")
    print(f"   assigned by curated name : {by_name:>4}/{n}  "
          f"({100*tw_named/tw:.1f}% of traffic)")
    print(f"   gravity-catchment fallback: {by_fallback:>4}/{n}")
    print(f"   dropped (no real city in basin): {dropped:>4}/{n}  "
          f"({100*tw_dropped/tw:.1f}% of traffic — remote islands, conservative bias)\n")

    print(f"2. Geometric sanity  (assignments > {_FAR_KM:.0f} km flagged)")
    print(f"   flagged: {len(far_rows)}/{n - dropped}")
    for t, iata, of, got, d in sorted(far_rows, reverse=True)[:10]:
        print(f"     {iata} trf={t:>3}  '{of}' -> '{got}' ({d:.0f} km)")

    print("\n3. Hub aggregation (metros absorbing multiple airports)")
    for cid, c in metro_count.most_common(6):
        print(f"   {byid.loc[cid,'name']:<16} <- {c} airports")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "europe")

"""Build a GLOBAL ferry-route dump from OpenStreetMap, once.

There is no maintained pre-built global ferry dataset; OSM is the canonical
source and the only true single-file dump is the ~80 GB planet (which needs
osmium tooling to filter). Instead we fetch every ``route=ferry`` *way* with
its real geometry (real terminal coordinates) via Overpass on a fine global
grid — small cells keep each query light enough to return real geometry
without timing out — and merge everything into one cached dump
``data/raw/water/ferries_world.json``. After that it is a file, not an API
call; the water layer filters/snaps it per region.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from src.paths import ensure_dir, raw_dir

_OVERPASS = "https://overpass-api.de/api/interpreter"
_CELL = 20  # degrees; small enough that each cell's geometry returns quickly
_MIN_KM = 5.0  # drop sub-km river/canal crossings; keep real straits & sea ferries


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    rlat1, rlat2 = math.radians(a[0]), math.radians(b[0])
    dlat = rlat2 - rlat1
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))


def _query_cell(s: float, w: float, n: float, e: float) -> list[dict]:
    query = (
        f"[out:json][timeout:90];"
        f'way["route"="ferry"]["passenger"!="no"]({s},{w},{n},{e});'
        f"out geom;"
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        _OVERPASS, data=body, headers={"User-Agent": "netsci-disease-spread/0.1 (research)"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (trusted host)
        payload = json.loads(resp.read())
    routes = []
    for way in payload.get("elements", []):
        geom = way.get("geometry") or []
        if len(geom) < 2:
            continue
        a = (geom[0]["lat"], geom[0]["lon"])
        b = (geom[-1]["lat"], geom[-1]["lon"])
        if _km(a, b) >= _MIN_KM:  # keep meaningful crossings, drop river ferries
            routes.append({"name": way.get("tags", {}).get("name", ""), "a": a, "b": b})
    return routes


def fetch(dest: Path | None = None, pause: float = 1.0, verbose: bool = True) -> Path:
    """Sweep a global grid of cells, fetch ferry ways with real geometry, and
    write one merged, deduplicated dump. Cells that error/timeout are skipped."""
    out = ensure_dir(dest or raw_dir("water"))
    seen: set[tuple] = set()
    routes: list[dict] = []
    skipped = 0
    lats = range(-60, 80, _CELL)
    lons = range(-180, 180, _CELL)
    for s in lats:
        for w in lons:
            try:
                cell = _query_cell(s, w, s + _CELL, w + _CELL)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                skipped += 1
                continue
            for r in cell:
                key = (
                    round(r["a"][0], 3), round(r["a"][1], 3),
                    round(r["b"][0], 3), round(r["b"][1], 3),
                )
                if key not in seen:
                    seen.add(key)
                    routes.append(r)
            if cell and verbose:
                print(f"  cell ({s},{w}): +{len(cell)} routes (total {len(routes)})")
            time.sleep(pause)  # be polite to the public Overpass instance

    (out / "ferries_world.json").write_text(json.dumps(routes))
    (out / "PROVENANCE.txt").write_text(
        f"OSM ferry ways (global grid, {_CELL}deg cells) — {date.today().isoformat()}\n"
        f"  source: Overpass API, way[route=ferry], ODbL\n"
        f"  total unique routes: {len(routes)}  (cells skipped on error: {skipped})\n"
    )
    return out

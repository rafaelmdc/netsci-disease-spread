"""Build a GLOBAL ferry-route dump for the water layer.

There is no maintained pre-built global ferry dataset; OSM is the canonical
source and the only true single-file dump is the ~80 GB planet (which needs
osmium tooling to filter). So we fetch every ``route=ferry`` *way* with its real
geometry (real terminal coordinates) via Overpass on a fine global grid — small
cells keep each query light enough to return real geometry without timing out —
and merge everything into one dump ``data/raw/water/ferries_world.json``.

A live Overpass sweep is slow, rate-limited, and non-reproducible, so it is
**not** the default. ``fetch`` resolves the dump in this order:

1. ``data/raw/water/ferries_world.json`` already present  -> use it (no network).
2. a vendored snapshot at ``vendor/ferries_world.json``   -> copy it (no network).
3. otherwise (or ``force=True``)                          -> live Overpass sweep.

After step 1/2 the water layer just filters/snaps a file, not an API call.
"""

from __future__ import annotations

import json
import math
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from src.paths import ROOT, ensure_dir, raw_dir

# Public Overpass mirrors, tried in order per cell before giving up on it.
_OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
)
_VENDOR_SNAPSHOT = ROOT / "vendor" / "ferries_world.json"
_CELL = 20  # degrees; small enough that each cell's geometry returns quickly
_MIN_KM = 5.0  # drop sub-km river/canal crossings; keep real straits & sea ferries
_RETRIES = 2  # extra attempts per mirror on transient errors


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    rlat1, rlat2 = math.radians(a[0]), math.radians(b[0])
    dlat = rlat2 - rlat1
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))


def _query_cell(s: float, w: float, n: float, e: float) -> list[dict]:
    """Fetch ferry ways in one cell, trying each mirror with a short backoff.

    Raises the last error only if every mirror/attempt fails for this cell.
    """
    query = (
        f"[out:json][timeout:90];"
        f'way["route"="ferry"]["passenger"!="no"]({s},{w},{n},{e});'
        f"out geom;"
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    last_err: Exception | None = None
    for endpoint in _OVERPASS_MIRRORS:
        for attempt in range(_RETRIES + 1):
            req = urllib.request.Request(
                endpoint, data=body, headers={"User-Agent": "netsci-disease-spread/0.1 (research)"}
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (trusted host)
                    payload = json.loads(resp.read())
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as err:
                last_err = err
                time.sleep(2.0 * (attempt + 1))  # backoff before the next try/mirror
        else:
            continue  # this mirror exhausted its retries; try the next one
        break  # got a payload
    else:
        raise last_err if last_err else RuntimeError("overpass: all mirrors failed")

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


def _live_sweep(out: Path, pause: float, verbose: bool) -> Path:
    """Sweep a global grid, fetch ferry ways, write one merged, deduplicated dump."""
    seen: set[tuple] = set()
    routes: list[dict] = []
    skipped = 0
    for s in range(-60, 80, _CELL):
        for w in range(-180, 180, _CELL):
            try:
                cell = _query_cell(s, w, s + _CELL, w + _CELL)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError):
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
        f"OSM ferry ways (live global grid, {_CELL}deg cells) — {date.today().isoformat()}\n"
        f"  source: Overpass API, way[route=ferry], ODbL\n"
        f"  total unique routes: {len(routes)}  (cells skipped on error: {skipped})\n"
    )
    return out


def fetch(dest: Path | None = None, force: bool = False, pause: float = 1.0,
          verbose: bool = True) -> Path:
    """Resolve the global ferry dump (cache -> vendored snapshot -> live sweep).

    With ``force=True`` always runs a fresh live Overpass sweep.
    """
    out = ensure_dir(dest or raw_dir("water"))
    target = out / "ferries_world.json"

    if target.exists() and not force:
        if verbose:
            print(f"  ferries: using cached {target} (use --force to refetch)")
        return out

    if _VENDOR_SNAPSHOT.exists() and not force:
        shutil.copyfile(_VENDOR_SNAPSHOT, target)
        n = len(json.loads(target.read_text()))
        (out / "PROVENANCE.txt").write_text(
            f"OSM ferry ways (vendored snapshot) — copied {date.today().isoformat()}\n"
            f"  source: vendor/ferries_world.json (Overpass API, way[route=ferry], ODbL)\n"
            f"  total unique routes: {n}\n"
        )
        if verbose:
            print(f"  ferries: copied vendored snapshot ({n} routes) -> {target}")
        return out

    if verbose:
        print("  ferries: live Overpass sweep (slow; use the vendored snapshot to skip)")
    return _live_sweep(out, pause, verbose)

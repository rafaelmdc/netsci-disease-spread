"""Download GeoNames city data — real cities with real populations.

cities15000 = every city with population > 15000 (name, lat/lon, country,
population, timezone). This is the canonical node set: layers attach to
cities, not airports, so ground mobility is modelled on the right entities.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from src.paths import ensure_dir, raw_dir

_URL = "http://download.geonames.org/export/dump/cities15000.zip"


def fetch(dest: Path | None = None) -> Path:
    """Download + unzip cities15000.txt into data/raw/geonames/."""
    out = ensure_dir(dest or raw_dir("geonames"))
    with urllib.request.urlopen(_URL, timeout=120) as resp:  # noqa: S310 (trusted host)
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extract("cities15000.txt", out)
    (out / "PROVENANCE.txt").write_text(
        f"GeoNames cities15000 — retrieved {date.today().isoformat()}\n  url: {_URL}\n"
    )
    return out

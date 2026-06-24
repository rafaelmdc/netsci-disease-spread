"""Download GeoNames city data — real cities with real populations.

cities1000 = every populated place with population > 1000 (plus seats of
admin divisions regardless of size), with name, lat/lon, country, population
and timezone. This is the canonical node set: layers attach to cities, not
airports, so ground mobility is modelled on the right entities. We use the
1000-tier (not 15000) so that small towns and remote islands — which many
airports and ferries serve — have a real node to attach to instead of being
dropped (see scripts/validate_snap.py). Airports whose served place is below
even this floor get an airport-as-node fallback in netgen.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from src.paths import ensure_dir, raw_dir

_TIER = "cities1000"
_URL = f"http://download.geonames.org/export/dump/{_TIER}.zip"


def fetch(dest: Path | None = None) -> Path:
    """Download + unzip cities1000.txt into data/raw/geonames/."""
    out = ensure_dir(dest or raw_dir("geonames"))
    with urllib.request.urlopen(_URL, timeout=180) as resp:  # noqa: S310 (trusted host)
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extract(f"{_TIER}.txt", out)
    (out / "PROVENANCE.txt").write_text(
        f"GeoNames {_TIER} — retrieved {date.today().isoformat()}\n  url: {_URL}\n"
    )
    return out

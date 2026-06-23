"""Download the OpenFlights airports + routes data (the air layer)."""

from __future__ import annotations

import hashlib
import urllib.request
from datetime import date
from pathlib import Path

from src.paths import ensure_dir, raw_dir

_BASE = "https://raw.githubusercontent.com/jpatokal/openflights/master/data"
_FILES = {"airports.dat": f"{_BASE}/airports.dat", "routes.dat": f"{_BASE}/routes.dat"}


def fetch(dest: Path | None = None) -> Path:
    """Download raw OpenFlights files to data/raw/air/ and write PROVENANCE.txt."""
    out = ensure_dir(dest or raw_dir("air"))
    lines = [f"OpenFlights air data — retrieved {date.today().isoformat()}", ""]
    for name, url in _FILES.items():
        target = out / name
        urllib.request.urlretrieve(url, target)  # noqa: S310 (trusted host)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        lines.append(f"{name}\n  url: {url}\n  sha256: {digest}")
    (out / "PROVENANCE.txt").write_text("\n".join(lines) + "\n")
    return out

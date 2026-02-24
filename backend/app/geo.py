from __future__ import annotations

from typing import Any

import h3


def latlng_to_h3_cell(lat: float, lon: float, resolution: int) -> str:
    if hasattr(h3, "latlng_to_cell"):
        return str(h3.latlng_to_cell(lat, lon, resolution))
    if hasattr(h3, "geo_to_h3"):
        return str(h3.geo_to_h3(lat, lon, resolution))
    msg = "Unsupported h3 package version: missing lat/lon to cell conversion API"
    raise RuntimeError(msg)


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

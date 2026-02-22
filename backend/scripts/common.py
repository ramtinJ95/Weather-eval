from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import h3
import requests


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def request_json(
    session: requests.Session,
    url: str,
    *,
    retries: int = 3,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                msg = f"Expected object JSON from {url}"
                raise ValueError(msg)
            return payload
        except Exception as exc:  # noqa: BLE001
            error = exc
            if attempt < retries:
                time.sleep(attempt)
    assert error is not None
    raise error


def download_text(
    session: requests.Session,
    url: str,
    *,
    retries: int = 3,
    timeout_seconds: int = 120,
) -> str:
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as exc:  # noqa: BLE001
            error = exc
            if attempt < retries:
                time.sleep(attempt)
    assert error is not None
    raise error


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.geo import latlng_to_h3_cell
from app.main import app, get_metrics_store
from app.weather_metrics import haversine_km


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in payload:
            handle.write(json.dumps(row) + "\n")


def test_haversine_km() -> None:
    stockholm = (59.3293, 18.0686)
    gothenburg = (57.7089, 11.9746)
    distance = haversine_km(stockholm[0], stockholm[1], gothenburg[0], gothenburg[1])
    assert 390 <= distance <= 410


def test_metrics_endpoint_with_sample_data(tmp_path: Path) -> None:
    lat = 59.3293
    lon = 18.0686
    h3_cell = latlng_to_h3_cell(lat, lon, 7)

    processed = tmp_path / "processed"
    _write_json(
        processed / "station_index.json",
        [
            {
                "station_id": "98210",
                "name": "Stockholm A",
                "lat": 59.353,
                "lon": 18.063,
            },
            {
                "station_id": "98230",
                "name": "Bromma",
                "lat": 59.354,
                "lon": 17.942,
            },
        ],
    )

    _write_jsonl(
        processed / "lightning_h3_r7_daily.jsonl",
        [
            {"h3": h3_cell, "date": "2025-07-01", "strike_count": 2},
            {"h3": h3_cell, "date": "2025-07-02", "strike_count": 5},
        ],
    )
    _write_json(
        processed / "lightning_h3_r7_monthly.json",
        [
            {
                "h3": h3_cell,
                "year": 2025,
                "month": 7,
                "strike_count": 7,
                "days_with_strike": 2,
                "days_in_month": 31,
                "strike_probability": 2 / 31,
            }
        ],
    )
    _write_json(
        processed / "lightning_h3_r7_yearly.json",
        [
            {
                "h3": h3_cell,
                "year": 2025,
                "strike_count": 7,
                "days_with_strike": 2,
                "days_in_year": 365,
                "strike_probability": 2 / 365,
            }
        ],
    )

    _write_jsonl(
        processed / "cloud_station_daily.jsonl",
        [
            {"station_id": "98210", "date": "2025-07-01", "cloud_mean_pct": 80.0},
            {"station_id": "98210", "date": "2025-07-02", "cloud_mean_pct": 65.0},
            {"station_id": "98230", "date": "2025-07-01", "cloud_mean_pct": 60.0},
            {"station_id": "98230", "date": "2025-07-02", "cloud_mean_pct": 45.0},
        ],
    )
    _write_json(
        processed / "cloud_station_monthly.json",
        [
            {"station_id": "98210", "year": 2025, "month": 7, "cloud_mean_pct": 72.5},
            {"station_id": "98230", "year": 2025, "month": 7, "cloud_mean_pct": 52.5},
        ],
    )
    _write_json(
        processed / "cloud_station_yearly.json",
        [
            {"station_id": "98210", "year": 2025, "cloud_mean_pct": 69.0},
            {"station_id": "98230", "year": 2025, "cloud_mean_pct": 49.0},
        ],
    )

    old_processed_dir = settings.processed_data_dir
    settings.processed_data_dir = processed
    get_metrics_store.cache_clear()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/metrics/point",
            json={"lat": lat, "lon": lon, "year": 2025, "month": 7},
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["point"]["h3_r7"] == h3_cell

        interpolation = payload["cloud_interpolation"]
        assert interpolation is not None
        assert interpolation["nearest_station_distance_km"] > 0

        assert payload["daily"]["days"][0]["lightning_count"] == 2
        day1_cloud = payload["daily"]["days"][0]["cloud_mean_pct"]
        assert day1_cloud is not None
        assert 60.0 < day1_cloud < 80.0

        day2_cloud = payload["daily"]["days"][1]["cloud_mean_pct"]
        assert day2_cloud is not None
        assert 45.0 < day2_cloud < 65.0

        july = next(month for month in payload["monthly"]["months"] if month["month"] == 7)
        assert july["lightning_count"] == 7
        assert july["cloud_mean_pct"] is not None
        assert 52.5 < july["cloud_mean_pct"] < 72.5

        year_2025 = next(y for y in payload["yearly"]["years"] if y["year"] == 2025)
        assert year_2025["cloud_mean_pct"] is not None
        assert 49.0 < year_2025["cloud_mean_pct"] < 69.0
    finally:
        settings.processed_data_dir = old_processed_dir
        get_metrics_store.cache_clear()


def test_metrics_endpoint_rejects_point_outside_sweden() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/metrics/point",
        json={"lat": 10.0, "lon": 10.0, "year": 2025, "month": 7},
    )
    assert response.status_code == 400

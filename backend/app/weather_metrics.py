from __future__ import annotations

import calendar
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.geo import as_float, as_int, latlng_to_h3_cell
from app.schemas import (
    CloudStationInfo,
    DailyMetrics,
    DayMetric,
    MonthlyMetrics,
    MonthMetric,
    PointInfo,
    PointMetricsResponse,
    YearlyMetrics,
    YearMetric,
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    lat: float
    lon: float
    active: bool


def _find_nearest(
    candidates: list[Station], lat: float, lon: float
) -> tuple[Station, float] | None:
    if not candidates:
        return None

    winner: Station | None = None
    winner_distance = float("inf")
    for station in candidates:
        distance = haversine_km(lat, lon, station.lat, station.lon)
        if distance < winner_distance:
            winner = station
            winner_distance = distance

    if winner is None:
        return None
    return winner, winner_distance


class MetricsStore:
    def __init__(
        self,
        *,
        stations: list[Station],
        lightning_daily: dict[tuple[str, str], int],
        lightning_monthly: dict[tuple[str, int, int], dict[str, Any]],
        lightning_yearly: dict[tuple[str, int], dict[str, Any]],
        cloud_daily: dict[tuple[str, str], float],
        cloud_monthly: dict[tuple[str, int, int], float],
        cloud_yearly: dict[tuple[str, int], float],
        start_year: int,
        h3_resolution: int,
        bounds: tuple[float, float, float, float],
    ) -> None:
        self.stations = stations
        self.lightning_daily = lightning_daily
        self.lightning_monthly = lightning_monthly
        self.lightning_yearly = lightning_yearly
        self.cloud_daily = cloud_daily
        self.cloud_monthly = cloud_monthly
        self.cloud_yearly = cloud_yearly
        self.start_year = start_year
        self.h3_resolution = h3_resolution
        self.bounds = bounds
        self.stations_with_any_cloud_data = {station_id for station_id, _year in self.cloud_yearly}

    @classmethod
    def from_processed_dir(
        cls,
        processed_dir: Path,
        *,
        start_year: int,
        h3_resolution: int,
        bounds: tuple[float, float, float, float],
    ) -> MetricsStore:
        stations = _load_station_index(processed_dir / "station_index.json")

        lightning_daily = _load_lightning_daily(processed_dir / "lightning_h3_r7_daily.jsonl")
        lightning_monthly = _load_lightning_monthly(processed_dir / "lightning_h3_r7_monthly.json")
        lightning_yearly = _load_lightning_yearly(processed_dir / "lightning_h3_r7_yearly.json")

        cloud_daily = _load_cloud_daily(processed_dir / "cloud_station_daily.jsonl")
        cloud_monthly = _load_cloud_monthly(processed_dir / "cloud_station_monthly.json")
        cloud_yearly = _load_cloud_yearly(processed_dir / "cloud_station_yearly.json")

        return cls(
            stations=stations,
            lightning_daily=lightning_daily,
            lightning_monthly=lightning_monthly,
            lightning_yearly=lightning_yearly,
            cloud_daily=cloud_daily,
            cloud_monthly=cloud_monthly,
            cloud_yearly=cloud_yearly,
            start_year=start_year,
            h3_resolution=h3_resolution,
            bounds=bounds,
        )

    def is_point_in_bounds(self, lat: float, lon: float) -> bool:
        min_lat, max_lat, min_lon, max_lon = self.bounds
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

    def nearest_station(self, lat: float, lon: float) -> tuple[Station, float] | None:
        return _find_nearest(self.stations, lat, lon)

    def nearest_station_with_cloud_data(
        self, lat: float, lon: float, *, year: int, month: int
    ) -> tuple[Station, float] | None:
        candidates = [
            station
            for station in self.stations
            if (station.station_id, year, month) in self.cloud_monthly
            or (station.station_id, year) in self.cloud_yearly
        ]
        return _find_nearest(candidates, lat, lon)

    def nearest_station_with_any_cloud_data(
        self, lat: float, lon: float
    ) -> tuple[Station, float] | None:
        candidates = [
            station
            for station in self.stations
            if station.station_id in self.stations_with_any_cloud_data
        ]
        return _find_nearest(candidates, lat, lon)

    def query(self, *, lat: float, lon: float, year: int, month: int) -> PointMetricsResponse:
        h3_cell = latlng_to_h3_cell(lat, lon, self.h3_resolution)
        station_match = self.nearest_station_with_cloud_data(lat, lon, year=year, month=month)
        if station_match is None:
            station_match = self.nearest_station_with_any_cloud_data(lat, lon)
        if station_match is None:
            station_match = self.nearest_station(lat, lon)
        station: Station | None = None
        station_info: CloudStationInfo | None = None
        if station_match is not None:
            station, distance_km = station_match
            station_info = CloudStationInfo(
                station_id=station.station_id,
                name=station.name,
                distance_km=round(distance_km, 2),
            )

        days = self._build_daily_series(h3_cell=h3_cell, station=station, year=year, month=month)
        months = self._build_monthly_series(h3_cell=h3_cell, station=station, year=year)
        years = self._build_yearly_series(h3_cell=h3_cell, station=station, selected_year=year)

        return PointMetricsResponse(
            point=PointInfo(lat=lat, lon=lon, h3_r7=h3_cell),
            cloud_station=station_info,
            daily=DailyMetrics(days=days),
            monthly=MonthlyMetrics(months=months),
            yearly=YearlyMetrics(years=years),
        )

    def _build_daily_series(
        self, *, h3_cell: str, station: Station | None, year: int, month: int
    ) -> list[DayMetric]:
        days_in_month = calendar.monthrange(year, month)[1]
        out: list[DayMetric] = []
        for day in range(1, days_in_month + 1):
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            lightning_count = self.lightning_daily.get((h3_cell, date_str), 0)
            cloud_mean_pct = None
            if station is not None:
                cloud_mean_pct = self.cloud_daily.get((station.station_id, date_str))

            out.append(
                DayMetric(
                    date=date_str,
                    cloud_mean_pct=cloud_mean_pct,
                    lightning_count=lightning_count,
                )
            )
        return out

    def _build_monthly_series(
        self, *, h3_cell: str, station: Station | None, year: int
    ) -> list[MonthMetric]:
        out: list[MonthMetric] = []
        for month in range(1, 13):
            lightning = self.lightning_monthly.get((h3_cell, year, month), {})
            lightning_count = int(lightning.get("strike_count", 0))
            lightning_probability = float(lightning.get("strike_probability", 0.0))

            cloud_mean_pct = None
            if station is not None:
                cloud_mean_pct = self.cloud_monthly.get((station.station_id, year, month))

            out.append(
                MonthMetric(
                    month=month,
                    cloud_mean_pct=cloud_mean_pct,
                    lightning_probability=lightning_probability,
                    lightning_count=lightning_count,
                )
            )
        return out

    def _build_yearly_series(
        self, *, h3_cell: str, station: Station | None, selected_year: int
    ) -> list[YearMetric]:
        current_year = date.today().year
        end_year = min(max(selected_year, self.start_year), current_year)
        out: list[YearMetric] = []

        for year in range(self.start_year, end_year + 1):
            lightning = self.lightning_yearly.get((h3_cell, year), {})
            lightning_count = int(lightning.get("strike_count", 0))
            lightning_probability = float(lightning.get("strike_probability", 0.0))

            cloud_mean_pct = None
            if station is not None:
                cloud_mean_pct = self.cloud_yearly.get((station.station_id, year))

            out.append(
                YearMetric(
                    year=year,
                    cloud_mean_pct=cloud_mean_pct,
                    lightning_probability=lightning_probability,
                    lightning_count=lightning_count,
                )
            )
        return out


def _load_station_index(path: Path) -> list[Station]:
    if not path.exists():
        return []

    raw = _load_json(path)
    if not isinstance(raw, list):
        return []

    stations: list[Station] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        station_id = str(item.get("station_id", "")).strip()
        name = str(item.get("name", "")).strip()
        lat = as_float(item.get("lat"))
        lon = as_float(item.get("lon"))
        active = bool(item.get("active", False))
        if not station_id or not name or lat is None or lon is None:
            continue

        stations.append(Station(station_id=station_id, name=name, lat=lat, lon=lon, active=active))
    return stations


def _load_lightning_daily(path: Path) -> dict[tuple[str, str], int]:
    rows = _load_jsonl(path)
    out: dict[tuple[str, str], int] = {}
    for row in rows:
        h3_cell = str(row.get("h3", "")).strip()
        date_str = str(row.get("date", "")).strip()
        strike_count = int(row.get("strike_count", 0))
        if not h3_cell or not date_str:
            continue
        out[(h3_cell, date_str)] = strike_count
    return out


def _load_lightning_monthly(path: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    raw = _load_json(path)
    out: dict[tuple[str, int, int], dict[str, Any]] = {}
    if not isinstance(raw, list):
        return out

    for row in raw:
        if not isinstance(row, dict):
            continue
        h3_cell = str(row.get("h3", "")).strip()
        year = as_int(row.get("year"))
        month = as_int(row.get("month"))
        if not h3_cell or year is None or month is None:
            continue
        out[(h3_cell, year, month)] = row
    return out


def _load_lightning_yearly(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    raw = _load_json(path)
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not isinstance(raw, list):
        return out

    for row in raw:
        if not isinstance(row, dict):
            continue
        h3_cell = str(row.get("h3", "")).strip()
        year = as_int(row.get("year"))
        if not h3_cell or year is None:
            continue
        out[(h3_cell, year)] = row
    return out


def _load_cloud_daily(path: Path) -> dict[tuple[str, str], float]:
    rows = _load_jsonl(path)
    out: dict[tuple[str, str], float] = {}
    for row in rows:
        station_id = str(row.get("station_id", "")).strip()
        date_str = str(row.get("date", "")).strip()
        cloud_mean_pct = as_float(row.get("cloud_mean_pct"))
        if not station_id or not date_str or cloud_mean_pct is None:
            continue
        out[(station_id, date_str)] = cloud_mean_pct
    return out


def _load_cloud_monthly(path: Path) -> dict[tuple[str, int, int], float]:
    raw = _load_json(path)
    out: dict[tuple[str, int, int], float] = {}
    if not isinstance(raw, list):
        return out

    for row in raw:
        if not isinstance(row, dict):
            continue
        station_id = str(row.get("station_id", "")).strip()
        year = as_int(row.get("year"))
        month = as_int(row.get("month"))
        cloud_mean_pct = as_float(row.get("cloud_mean_pct"))
        if not station_id or year is None or month is None or cloud_mean_pct is None:
            continue
        out[(station_id, year, month)] = cloud_mean_pct
    return out


def _load_cloud_yearly(path: Path) -> dict[tuple[str, int], float]:
    raw = _load_json(path)
    out: dict[tuple[str, int], float] = {}
    if not isinstance(raw, list):
        return out

    for row in raw:
        if not isinstance(row, dict):
            continue
        station_id = str(row.get("station_id", "")).strip()
        year = as_int(row.get("year"))
        cloud_mean_pct = as_float(row.get("cloud_mean_pct"))
        if not station_id or year is None or cloud_mean_pct is None:
            continue
        out[(station_id, year)] = cloud_mean_pct
    return out


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows

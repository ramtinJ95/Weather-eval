from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from common import write_json, write_jsonl


@dataclass(frozen=True)
class CloudObservation:
    date_str: str
    time_str: str
    value: float
    quality: str
    source_priority: int


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser(
        description="Build cloud station aggregates from corrected + latest-months CSV archives"
    )
    parser.add_argument(
        "--corrected-dir",
        type=Path,
        default=base_dir / "raw" / "cloud" / "station",
    )
    parser.add_argument(
        "--latest-months-dir",
        type=Path,
        default=base_dir / "raw" / "cloud" / "station_latest_months",
    )
    parser.add_argument("--output-dir", type=Path, default=base_dir / "processed")
    parser.add_argument("--start-date", type=str, default="2023-01-01")
    return parser.parse_args()


def _to_float(value: str) -> float | None:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _quality_rank(quality: str) -> int:
    if quality == "G":
        return 2
    if quality == "Y":
        return 1
    return 0


def _parse_station_csv(
    path: Path,
    *,
    station_id: str,
    start_date: date,
    source_priority: int,
) -> dict[tuple[str, str], CloudObservation]:
    observations: dict[tuple[str, str], CloudObservation] = {}

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header_index = -1
    for idx, line in enumerate(lines):
        if line.lstrip("\ufeff").startswith("Datum;Tid (UTC);"):
            header_index = idx
            break

    if header_index < 0:
        return observations

    for line in lines[header_index + 1 :]:
        if not line.strip():
            continue

        columns = line.split(";")
        if len(columns) < 4:
            continue

        date_str = columns[0].strip()
        time_str = columns[1].strip()
        value_str = columns[2].strip()
        quality = columns[3].strip().upper()

        if quality not in {"G", "Y"}:
            continue

        value = _to_float(value_str)
        if value is None or value > 100:
            continue

        try:
            day_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if day_date < start_date:
            continue

        key = (date_str, time_str)
        candidate = CloudObservation(
            date_str=date_str,
            time_str=time_str,
            value=value,
            quality=quality,
            source_priority=source_priority,
        )

        current = observations.get(key)
        if current is None:
            observations[key] = candidate
            continue

        if candidate.source_priority > current.source_priority:
            observations[key] = candidate
            continue
        if candidate.source_priority == current.source_priority and _quality_rank(
            candidate.quality
        ) > _quality_rank(current.quality):
            observations[key] = candidate

    return observations


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    start_date = date.fromisoformat(args.start_date)

    daily_sums: dict[tuple[str, str], float] = defaultdict(float)
    daily_counts: dict[tuple[str, str], int] = defaultdict(int)

    monthly_sums: dict[tuple[str, int, int], float] = defaultdict(float)
    monthly_counts: dict[tuple[str, int, int], int] = defaultdict(int)

    yearly_sums: dict[tuple[str, int], float] = defaultdict(float)
    yearly_counts: dict[tuple[str, int], int] = defaultdict(int)

    station_ids = {path.stem for path in args.corrected_dir.glob("*.csv")} | {
        path.stem for path in args.latest_months_dir.glob("*.csv")
    }

    for station_id in sorted(station_ids):
        merged_observations: dict[tuple[str, str], CloudObservation] = {}

        corrected_path = args.corrected_dir / f"{station_id}.csv"
        if corrected_path.exists():
            corrected_obs = _parse_station_csv(
                corrected_path,
                station_id=station_id,
                start_date=start_date,
                source_priority=2,
            )
            merged_observations.update(corrected_obs)

        latest_months_path = args.latest_months_dir / f"{station_id}.csv"
        if latest_months_path.exists():
            latest_obs = _parse_station_csv(
                latest_months_path,
                station_id=station_id,
                start_date=start_date,
                source_priority=1,
            )
            for key, value in latest_obs.items():
                current = merged_observations.get(key)
                should_replace = (
                    current is None
                    or value.source_priority > current.source_priority
                    or (
                        value.source_priority == current.source_priority
                        and _quality_rank(value.quality) > _quality_rank(current.quality)
                    )
                )
                if should_replace:
                    merged_observations[key] = value

        for observation in merged_observations.values():
            day_date = date.fromisoformat(observation.date_str)
            day_key = day_date.isoformat()

            daily_sums[(station_id, day_key)] += observation.value
            daily_counts[(station_id, day_key)] += 1

            monthly_sums[(station_id, day_date.year, day_date.month)] += observation.value
            monthly_counts[(station_id, day_date.year, day_date.month)] += 1

            yearly_sums[(station_id, day_date.year)] += observation.value
            yearly_counts[(station_id, day_date.year)] += 1

    daily_rows: list[dict[str, Any]] = []
    for (station_id, date_str), value_sum in sorted(daily_sums.items()):
        count = daily_counts[(station_id, date_str)]
        year, month, day = map(int, date_str.split("-"))
        daily_rows.append(
            {
                "station_id": station_id,
                "date": date_str,
                "year": year,
                "month": month,
                "day": day,
                "cloud_mean_pct": round(value_sum / count, 3),
                "n_samples": count,
            }
        )

    monthly_rows: list[dict[str, Any]] = []
    for (station_id, year, month), value_sum in sorted(monthly_sums.items()):
        count = monthly_counts[(station_id, year, month)]
        monthly_rows.append(
            {
                "station_id": station_id,
                "year": year,
                "month": month,
                "cloud_mean_pct": round(value_sum / count, 3),
                "n_samples": count,
            }
        )

    yearly_rows: list[dict[str, Any]] = []
    for (station_id, year), value_sum in sorted(yearly_sums.items()):
        count = yearly_counts[(station_id, year)]
        yearly_rows.append(
            {
                "station_id": station_id,
                "year": year,
                "cloud_mean_pct": round(value_sum / count, 3),
                "n_samples": count,
            }
        )

    write_jsonl(args.output_dir / "cloud_station_daily.jsonl", daily_rows)
    write_json(args.output_dir / "cloud_station_monthly.json", monthly_rows)
    write_json(args.output_dir / "cloud_station_yearly.json", yearly_rows)

    print(
        "Cloud aggregates done. "
        f"daily={len(daily_rows)} monthly={len(monthly_rows)} yearly={len(yearly_rows)}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from common import ensure_parent, write_json


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser(description="Build cloud station aggregates from CSV archives")
    parser.add_argument("--input-dir", type=Path, default=base_dir / "raw" / "cloud" / "station")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "processed")
    parser.add_argument("--start-date", type=str, default="2021-01-01")
    return parser.parse_args()


def _to_float(value: str) -> float | None:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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

    for station_csv in sorted(args.input_dir.glob("*.csv")):
        station_id = station_csv.stem
        lines = station_csv.read_text(encoding="utf-8", errors="replace").splitlines()

        header_index = -1
        for idx, line in enumerate(lines):
            if line.lstrip("\ufeff").startswith("Datum;Tid (UTC);"):
                header_index = idx
                break

        if header_index < 0:
            continue

        for line in lines[header_index + 1 :]:
            if not line.strip():
                continue

            columns = line.split(";")
            if len(columns) < 4:
                continue

            date_str = columns[0].strip()
            value_str = columns[2].strip()
            quality = columns[3].strip().upper()

            if quality not in {"G", "Y"}:
                continue

            value = _to_float(value_str)
            if value is None:
                continue

            try:
                day_date = date.fromisoformat(date_str)
            except ValueError:
                continue
            if day_date < start_date:
                continue

            day_key = day_date.isoformat()
            month_key = (day_date.year, day_date.month)
            year_key = day_date.year

            daily_sums[(station_id, day_key)] += value
            daily_counts[(station_id, day_key)] += 1

            monthly_sums[(station_id, month_key[0], month_key[1])] += value
            monthly_counts[(station_id, month_key[0], month_key[1])] += 1

            yearly_sums[(station_id, year_key)] += value
            yearly_counts[(station_id, year_key)] += 1

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

    _write_jsonl(args.output_dir / "cloud_station_daily.jsonl", daily_rows)
    write_json(args.output_dir / "cloud_station_monthly.json", monthly_rows)
    write_json(args.output_dir / "cloud_station_yearly.json", yearly_rows)

    print(
        "Cloud aggregates done. "
        f"daily={len(daily_rows)} monthly={len(monthly_rows)} yearly={len(yearly_rows)}"
    )


if __name__ == "__main__":
    main()

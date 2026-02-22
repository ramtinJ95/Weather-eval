from __future__ import annotations

import argparse
import calendar
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from common import as_float, as_int, latlng_to_h3_cell, write_json, write_jsonl


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser(description="Build lightning aggregates by H3 r7")
    parser.add_argument("--input-dir", type=Path, default=base_dir / "raw" / "lightning")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "processed")
    parser.add_argument("--resolution", type=int, default=7)
    parser.add_argument("--start-year", type=int, default=2023)
    return parser.parse_args()


def _iter_rows(csv_path: Path):
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if row:
                yield row


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    daily_counts: dict[tuple[str, str], int] = defaultdict(int)
    monthly_counts: dict[tuple[str, int, int], int] = defaultdict(int)
    yearly_counts: dict[tuple[str, int], int] = defaultdict(int)

    csv_files = sorted(args.input_dir.glob("*/*/*.csv"))
    for csv_file in csv_files:
        for row in _iter_rows(csv_file):
            year = as_int(row.get("year"))
            month = as_int(row.get("month"))
            day = as_int(row.get("day"))
            lat = as_float(row.get("lat"))
            lon = as_float(row.get("lon"))

            if year is None or month is None or day is None or lat is None or lon is None:
                continue
            if year < args.start_year:
                continue

            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            h3_cell = latlng_to_h3_cell(lat, lon, args.resolution)

            daily_counts[(h3_cell, date_str)] += 1
            monthly_counts[(h3_cell, year, month)] += 1
            yearly_counts[(h3_cell, year)] += 1

    monthly_day_sets: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    yearly_day_sets: dict[tuple[str, int], set[str]] = defaultdict(set)

    for h3_cell, date_str in daily_counts:
        year, month, _day = map(int, date_str.split("-"))
        monthly_day_sets[(h3_cell, year, month)].add(date_str)
        yearly_day_sets[(h3_cell, year)].add(date_str)

    daily_rows = [
        {"h3": h3_cell, "date": date_str, "strike_count": strike_count}
        for (h3_cell, date_str), strike_count in sorted(daily_counts.items())
    ]

    monthly_rows: list[dict[str, Any]] = []
    for (h3_cell, year, month), strike_count in sorted(monthly_counts.items()):
        days_in_month = calendar.monthrange(year, month)[1]
        days_with_strike = len(monthly_day_sets[(h3_cell, year, month)])
        monthly_rows.append(
            {
                "h3": h3_cell,
                "year": year,
                "month": month,
                "strike_count": strike_count,
                "days_with_strike": days_with_strike,
                "days_in_month": days_in_month,
                "strike_probability": round(days_with_strike / days_in_month, 6),
            }
        )

    yearly_rows: list[dict[str, Any]] = []
    for (h3_cell, year), strike_count in sorted(yearly_counts.items()):
        days_in_year = date(year, 12, 31).timetuple().tm_yday
        days_with_strike = len(yearly_day_sets[(h3_cell, year)])
        yearly_rows.append(
            {
                "h3": h3_cell,
                "year": year,
                "strike_count": strike_count,
                "days_with_strike": days_with_strike,
                "days_in_year": days_in_year,
                "strike_probability": round(days_with_strike / days_in_year, 6),
            }
        )

    write_jsonl(args.output_dir / "lightning_h3_r7_daily.jsonl", daily_rows)
    write_json(args.output_dir / "lightning_h3_r7_monthly.json", monthly_rows)
    write_json(args.output_dir / "lightning_h3_r7_yearly.json", yearly_rows)

    print(
        "Lightning aggregates done. "
        f"daily={len(daily_rows)} monthly={len(monthly_rows)} yearly={len(yearly_rows)}"
    )


if __name__ == "__main__":
    main()

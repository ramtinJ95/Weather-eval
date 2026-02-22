from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate processed weather aggregates")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed",
    )
    parser.add_argument(
        "--cloud-tolerance",
        type=float,
        default=0.002,
        help="Allowed absolute mean-difference tolerance for cloud rolling-up checks",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    p = args.processed_dir

    _validate_lightning(p)
    _validate_cloud(p, tolerance=args.cloud_tolerance)

    print("Aggregate validation finished successfully.")


def _validate_lightning(processed: Path) -> None:
    monthly_rows = json.loads((processed / "lightning_h3_r7_monthly.json").read_text())
    yearly_rows = json.loads((processed / "lightning_h3_r7_yearly.json").read_text())

    monthly = {(r["h3"], r["year"], r["month"]): int(r["strike_count"]) for r in monthly_rows}
    yearly = {(r["h3"], r["year"]): int(r["strike_count"]) for r in yearly_rows}

    monthly_from_daily: dict[tuple[str, int, int], int] = defaultdict(int)
    yearly_from_daily: dict[tuple[str, int], int] = defaultdict(int)

    with (processed / "lightning_h3_r7_daily.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            year, month, _day = map(int, row["date"].split("-"))
            h3_cell = row["h3"]
            count = int(row["strike_count"])

            monthly_from_daily[(h3_cell, year, month)] += count
            yearly_from_daily[(h3_cell, year)] += count

    for key, value in monthly.items():
        expected = monthly_from_daily.get(key)
        if expected != value:
            raise ValueError(
                f"Lightning monthly mismatch for {key}: stored={value}, expected={expected}"
            )

    for key, value in yearly.items():
        expected = yearly_from_daily.get(key)
        if expected != value:
            raise ValueError(
                f"Lightning yearly mismatch for {key}: stored={value}, expected={expected}"
            )

    print(
        "Lightning aggregates validated: "
        f"monthly={len(monthly)} yearly={len(yearly)} all consistent"
    )


def _validate_cloud(processed: Path, *, tolerance: float) -> None:
    monthly_rows = json.loads((processed / "cloud_station_monthly.json").read_text())
    yearly_rows = json.loads((processed / "cloud_station_yearly.json").read_text())

    monthly = {
        (r["station_id"], r["year"], r["month"]): (float(r["cloud_mean_pct"]), int(r["n_samples"]))
        for r in monthly_rows
    }
    yearly = {
        (r["station_id"], r["year"]): (float(r["cloud_mean_pct"]), int(r["n_samples"]))
        for r in yearly_rows
    }

    monthly_sum: dict[tuple[str, int, int], float] = defaultdict(float)
    monthly_count: dict[tuple[str, int, int], int] = defaultdict(int)
    yearly_sum: dict[tuple[str, int], float] = defaultdict(float)
    yearly_count: dict[tuple[str, int], int] = defaultdict(int)

    with (processed / "cloud_station_daily.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            station_id = row["station_id"]
            year = int(row["year"])
            month = int(row["month"])
            day_mean = float(row["cloud_mean_pct"])
            day_samples = int(row["n_samples"])

            monthly_sum[(station_id, year, month)] += day_mean * day_samples
            monthly_count[(station_id, year, month)] += day_samples

            yearly_sum[(station_id, year)] += day_mean * day_samples
            yearly_count[(station_id, year)] += day_samples

    for key, (stored_mean, stored_samples) in monthly.items():
        expected_samples = monthly_count.get(key)
        if expected_samples != stored_samples:
            raise ValueError(
                f"Cloud monthly samples mismatch for {key}: "
                f"stored={stored_samples}, expected={expected_samples}"
            )

        expected_mean = monthly_sum[key] / expected_samples
        if abs(expected_mean - stored_mean) > tolerance:
            raise ValueError(
                f"Cloud monthly mean mismatch for {key}: "
                f"stored={stored_mean}, expected={expected_mean:.6f}"
            )

    for key, (stored_mean, stored_samples) in yearly.items():
        expected_samples = yearly_count.get(key)
        if expected_samples != stored_samples:
            raise ValueError(
                f"Cloud yearly samples mismatch for {key}: "
                f"stored={stored_samples}, expected={expected_samples}"
            )

        expected_mean = yearly_sum[key] / expected_samples
        if abs(expected_mean - stored_mean) > tolerance:
            raise ValueError(
                f"Cloud yearly mean mismatch for {key}: "
                f"stored={stored_mean}, expected={expected_mean:.6f}"
            )

    print(
        "Cloud aggregates validated: "
        f"monthly={len(monthly)} yearly={len(yearly)} all within tolerance={tolerance}"
    )


if __name__ == "__main__":
    main()

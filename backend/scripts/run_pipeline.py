from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full phase-1 data pipeline")
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip raw downloads and only build aggregates from existing raw files",
    )
    parser.add_argument(
        "--max-lightning-days",
        type=int,
        default=None,
        help="Optional cap for lightning day downloads (smoke testing)",
    )
    parser.add_argument(
        "--max-cloud-stations",
        type=int,
        default=None,
        help="Optional cap for cloud station downloads (smoke testing)",
    )
    return parser.parse_args()


def _run(script_name: str, *args: str) -> None:
    script_path = Path(__file__).resolve().parent / script_name
    command = [sys.executable, str(script_path), *args]
    print(f"\n==> Running: {' '.join(command)}")
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()

    if not args.skip_fetch:
        lightning_args = [
            "fetch_lightning_raw.py",
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(args.end_year),
        ]
        if args.max_lightning_days is not None:
            lightning_args.extend(["--max-days", str(args.max_lightning_days)])
        _run(*lightning_args)

        cloud_args = ["fetch_cloud_raw.py"]
        if args.max_cloud_stations is not None:
            cloud_args.extend(["--max-stations", str(args.max_cloud_stations)])
        _run(*cloud_args)

    _run("build_station_index.py")
    _run("build_lightning_aggregates.py", "--start-year", str(args.start_year))
    _run("build_cloud_aggregates.py", "--start-date", f"{args.start_year}-01-01")

    print("\nPipeline finished successfully.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import requests
from common import download_text, request_json, write_json

CLOUD_PARAMETER_URL = (
    "https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16.json"
)
CLOUD_STATION_CSV_URL_TEMPLATE = (
    "https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16/"
    "station/{station_id}/period/corrected-archive/data.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SMHI cloud (parameter 16) station CSV files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "raw" / "cloud",
    )
    parser.add_argument(
        "--max-stations",
        type=int,
        default=None,
        help="Optional cap for number of stations to download (useful for smoke tests)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    station_dir = args.output_dir / "station"
    station_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    metadata = request_json(session, CLOUD_PARAMETER_URL)
    write_json(args.output_dir / "parameter-16-stations.json", metadata)

    downloaded = 0
    skipped = 0
    failed: list[dict[str, str]] = []

    stations = metadata.get("station", [])
    for station in stations:
        if not isinstance(station, dict):
            continue
        if args.max_stations is not None and (downloaded + skipped) >= args.max_stations:
            break

        station_id = str(station.get("id", "")).strip()
        if not station_id:
            continue

        out_path = station_dir / f"{station_id}.csv"
        if out_path.exists():
            skipped += 1
            continue

        csv_url = CLOUD_STATION_CSV_URL_TEMPLATE.format(station_id=station_id)
        try:
            csv_body = download_text(session, csv_url)
            out_path.write_text(csv_body, encoding="utf-8")
            downloaded += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"station_id": station_id, "reason": str(exc)})

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "stations_total": len(stations),
        "downloaded": downloaded,
        "skipped_existing": skipped,
        "failed_count": len(failed),
        "failed": failed,
        "max_stations": args.max_stations,
    }
    write_json(args.output_dir / "manifest.json", report)
    write_json(args.output_dir / "failed_stations.json", failed)

    print(f"Cloud fetch done. downloaded={downloaded} skipped={skipped} failed={len(failed)}")


if __name__ == "__main__":
    main()

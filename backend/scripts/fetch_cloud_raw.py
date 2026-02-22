from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from common import download_text, request_json, write_json

CLOUD_PARAMETER_URL = (
    "https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16.json"
)
CLOUD_STATION_CORRECTED_CSV_URL_TEMPLATE = (
    "https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16/"
    "station/{station_id}/period/corrected-archive/data.csv"
)
CLOUD_STATION_LATEST_MONTHS_CSV_URL_TEMPLATE = (
    "https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16/"
    "station/{station_id}/period/latest-months/data.csv"
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
    parser.add_argument(
        "--latest-months-lookback-days",
        type=int,
        default=180,
        help=(
            "Only attempt latest-months for stations where metadata 'to' timestamp "
            "is within this many days from now"
        ),
    )
    parser.add_argument(
        "--show-progress-every",
        type=int,
        default=25,
        help="Print progress every N stations",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    corrected_station_dir = args.output_dir / "station"
    latest_months_station_dir = args.output_dir / "station_latest_months"
    corrected_station_dir.mkdir(parents=True, exist_ok=True)
    latest_months_station_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    metadata = request_json(session, CLOUD_PARAMETER_URL)
    write_json(args.output_dir / "parameter-16-stations.json", metadata)

    downloaded_corrected = 0
    skipped_corrected = 0
    failed_corrected: list[dict[str, str]] = []

    downloaded_latest_months = 0
    skipped_latest_months = 0
    failed_latest_months: list[dict[str, str]] = []
    skipped_latest_months_not_recent = 0

    now_utc = datetime.now(tz=UTC)
    lookback_seconds = args.latest_months_lookback_days * 24 * 60 * 60
    started_at = time.monotonic()

    stations = metadata.get("station", [])
    for idx, station in enumerate(stations, start=1):
        if not isinstance(station, dict):
            continue

        if (
            args.max_stations is not None
            and (downloaded_corrected + skipped_corrected) >= args.max_stations
        ):
            break

        station_id = str(station.get("id", "")).strip()
        if not station_id:
            continue

        station_to_ms = station.get("to")
        station_to_recent = False
        try:
            station_to_dt = datetime.fromtimestamp(int(station_to_ms) / 1000, tz=UTC)
            station_to_recent = (now_utc - station_to_dt).total_seconds() <= lookback_seconds
        except (TypeError, ValueError, OSError):
            station_to_recent = False

        corrected_out_path = corrected_station_dir / f"{station_id}.csv"
        latest_out_path = latest_months_station_dir / f"{station_id}.csv"

        if corrected_out_path.exists():
            skipped_corrected += 1
        else:
            corrected_csv_url = CLOUD_STATION_CORRECTED_CSV_URL_TEMPLATE.format(
                station_id=station_id
            )
            try:
                corrected_csv_body = download_text(session, corrected_csv_url)
                corrected_out_path.write_text(corrected_csv_body, encoding="utf-8")
                downloaded_corrected += 1
            except Exception as exc:  # noqa: BLE001
                failed_corrected.append({"station_id": station_id, "reason": str(exc)})

        if latest_out_path.exists():
            skipped_latest_months += 1
        elif not station_to_recent:
            skipped_latest_months_not_recent += 1
        else:
            latest_months_csv_url = CLOUD_STATION_LATEST_MONTHS_CSV_URL_TEMPLATE.format(
                station_id=station_id
            )
            try:
                latest_months_csv_body = download_text(
                    session,
                    latest_months_csv_url,
                    retries=1,
                    timeout_seconds=20,
                )
                latest_out_path.write_text(latest_months_csv_body, encoding="utf-8")
                downloaded_latest_months += 1
            except Exception as exc:  # noqa: BLE001
                failed_latest_months.append({"station_id": station_id, "reason": str(exc)})

        if idx % args.show_progress_every == 0:
            elapsed = round(time.monotonic() - started_at, 1)
            print(
                "progress "
                f"{idx}/{len(stations)} "
                "corrected("
                f"d={downloaded_corrected},"
                f"s={skipped_corrected},"
                f"f={len(failed_corrected)}"
                ") "
                f"latest(d={downloaded_latest_months},s={skipped_latest_months},"
                f"skip-old={skipped_latest_months_not_recent},f={len(failed_latest_months)}) "
                f"elapsed={elapsed}s"
            )

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "stations_total": len(stations),
        "corrected_archive": {
            "downloaded": downloaded_corrected,
            "skipped_existing": skipped_corrected,
            "failed_count": len(failed_corrected),
            "failed": failed_corrected,
        },
        "latest_months": {
            "downloaded": downloaded_latest_months,
            "skipped_existing": skipped_latest_months,
            "skipped_not_recent": skipped_latest_months_not_recent,
            "failed_count": len(failed_latest_months),
            "failed": failed_latest_months,
        },
        "latest_months_lookback_days": args.latest_months_lookback_days,
        "max_stations": args.max_stations,
    }
    write_json(args.output_dir / "manifest.json", report)
    write_json(
        args.output_dir / "failed_stations.json",
        {
            "corrected_archive": failed_corrected,
            "latest_months": failed_latest_months,
        },
    )

    print(
        "Cloud fetch done. "
        "corrected("
        f"downloaded={downloaded_corrected}, "
        f"skipped={skipped_corrected}, "
        f"failed={len(failed_corrected)}"
        ") "
        "latest-months("
        f"downloaded={downloaded_latest_months}, "
        f"skipped={skipped_latest_months}, "
        f"skipped-not-recent={skipped_latest_months_not_recent}, "
        f"failed={len(failed_latest_months)}"
        ")"
    )


if __name__ == "__main__":
    main()

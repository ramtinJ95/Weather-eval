from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import requests
from common import download_text, request_json, write_json

LIGHTNING_ROOT_URL = "https://opendata-download-lightning.smhi.se/api/version/latest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download SMHI lightning daily CSV files")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=datetime.now(tz=UTC).year)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "raw" / "lightning",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        help="Optional cap for number of day CSV files to download (for smoke tests)",
    )
    return parser.parse_args()


def _pick_link(payload: dict, rel: str) -> str | None:
    for link in payload.get("link", []):
        if isinstance(link, dict) and link.get("rel") == rel:
            href = link.get("href")
            if isinstance(href, str):
                return href
    return None


def _pick_csv_link(day_payload: dict) -> str | None:
    for data_item in day_payload.get("data", []):
        if not isinstance(data_item, dict):
            continue
        for link in data_item.get("link", []):
            if not isinstance(link, dict):
                continue
            href = link.get("href")
            if isinstance(href, str) and href.endswith(".csv"):
                return href
    return None


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    downloaded = 0
    skipped = 0
    failed: list[dict[str, str | int]] = []

    root = request_json(session, LIGHTNING_ROOT_URL)
    years: list[tuple[int, str]] = []
    for resource in root.get("resource", []):
        if not isinstance(resource, dict):
            continue
        year = int(resource.get("key", 0))
        if not (args.start_year <= year <= args.end_year):
            continue
        year_link = _pick_link(resource, "year")
        if year_link is None:
            continue
        years.append((year, year_link))

    for year, year_url in sorted(years):
        if args.max_days is not None and downloaded >= args.max_days:
            break

        year_payload = request_json(session, year_url)
        month_items = year_payload.get("month", [])
        for month_item in month_items:
            if not isinstance(month_item, dict):
                continue
            if args.max_days is not None and downloaded >= args.max_days:
                break

            month = int(month_item.get("key", 0))
            month_url = _pick_link(month_item, "month")
            if month_url is None:
                continue

            month_payload = request_json(session, month_url)
            day_items = month_payload.get("day", [])
            for day_item in day_items:
                if not isinstance(day_item, dict):
                    continue
                if args.max_days is not None and downloaded >= args.max_days:
                    break

                day = int(day_item.get("key", 0))
                day_url = _pick_link(day_item, "day")
                if day_url is None:
                    continue

                target_path = args.output_dir / f"{year}" / f"{month:02d}" / f"{day:02d}.csv"
                if target_path.exists():
                    skipped += 1
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    day_payload = request_json(session, day_url)
                    csv_url = _pick_csv_link(day_payload)
                    if csv_url is None:
                        failed.append(
                            {
                                "year": year,
                                "month": month,
                                "day": day,
                                "reason": "no-csv",
                            }
                        )
                        continue

                    csv_body = download_text(session, csv_url)
                    target_path.write_text(csv_body, encoding="utf-8")
                    downloaded += 1
                except Exception as exc:  # noqa: BLE001
                    failed.append(
                        {
                            "year": year,
                            "month": month,
                            "day": day,
                            "reason": str(exc),
                        }
                    )

    manifest = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "downloaded": downloaded,
        "skipped_existing": skipped,
        "failed_count": len(failed),
        "failed": failed,
        "max_days": args.max_days,
    }
    write_json(args.output_dir / "manifest.json", manifest)

    print(f"Lightning fetch done. downloaded={downloaded} skipped={skipped} failed={len(failed)}")


if __name__ == "__main__":
    main()

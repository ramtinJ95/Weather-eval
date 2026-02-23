from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import as_float, write_json


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser(
        description="Build normalized station index for cloud parameter 16"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=base_dir / "raw" / "cloud" / "parameter-16-stations.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=base_dir / "processed" / "station_index.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        msg = f"Input file does not exist: {args.input}"
        raise FileNotFoundError(msg)

    import json

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = "Unexpected station metadata JSON format"
        raise ValueError(msg)

    stations_out: list[dict[str, Any]] = []
    for station in payload.get("station", []):
        if not isinstance(station, dict):
            continue

        station_id = str(station.get("id", "")).strip()
        name = str(station.get("name", "")).strip()
        lat = as_float(station.get("latitude"))
        lon = as_float(station.get("longitude"))

        if not station_id or not name or lat is None or lon is None:
            continue

        stations_out.append(
            {
                "station_id": station_id,
                "name": name,
                "lat": lat,
                "lon": lon,
            }
        )

    write_json(args.output, stations_out)
    print(f"Wrote {len(stations_out)} stations to {args.output}")


if __name__ == "__main__":
    main()

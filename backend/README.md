# Backend

FastAPI backend for weather-eval.

## Phase 1 data pipeline

Run once to download raw data and build aggregates:

```bash
cd backend
uv sync --dev
uv run python scripts/run_pipeline.py --start-year 2021 --end-year 2026
```

Cloud fetch now downloads both:
- `corrected-archive` (historical)
- `latest-months` (recent values, used to include 2026)

The cloud fetcher avoids unnecessary latest-months calls for stations whose
metadata indicates old/inactive data, and prints progress while running.

If raw files already exist and you only want to rebuild aggregates:

```bash
cd backend
uv run python scripts/run_pipeline.py --skip-fetch --start-year 2021 --end-year 2026
```

Quick smoke-test run (small subset):

```bash
cd backend
uv run python scripts/run_pipeline.py \
  --start-year 2026 --end-year 2026 \
  --max-lightning-days 5 \
  --max-cloud-stations 10
```

Outputs are written to:

- `backend/data/raw/...`
- `backend/data/processed/...`

## Metrics API

Endpoint:

- `POST /api/metrics/point`

Request body:

```json
{
  "lat": 59.3293,
  "lon": 18.0686,
  "year": 2025,
  "month": 7
}
```

The endpoint returns:

- selected point info + H3 cell
- nearest cloud station
- daily metrics for selected month
- monthly metrics for selected year
- yearly metrics from 2021 up to selected year/current year

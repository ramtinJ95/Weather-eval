# weather-eval

Monorepo for:
- React + TypeScript frontend (`frontend/`)
- FastAPI backend (`backend/`)
- single Docker image serving both
- Terraform on GCP (`infra/`)
- GitHub Actions CI/CD (`.github/workflows/`)

This project now includes a **Phase 1 local-first weather analytics pipeline**
for Sweden using SMHI lightning + cloud-cover observations.

## What works now

- `/api/health` returns backend health
- `/api/hello` reads from Firestore and falls back to default text
- `/api/metrics/point` returns cloud/lightning metrics for a selected lat/lon
- frontend includes a map-click workflow + day/month/year charts
- Docker image builds frontend and serves it from FastAPI

## Fast start (recommended)

Start backend + frontend with one command:

```bash
make run
```

Then open: http://localhost:5173

## Data pipeline commands

Full dataset (2021–2026):

```bash
make pipeline
```

Smoke test subset:

```bash
make pipeline-smoke
```

Validate aggregate consistency:

```bash
make validate-aggregates
```

Fetch only lightning (2021–2026):

```bash
make fetch-lightning
```

Refresh cloud data (corrected-archive + latest-months, then rebuild cloud aggregates):

```bash
make refresh-cloud
```

Upload local processed artifacts to GCS (used by deploy workflow image build):

```bash
scripts/upload_processed_to_gcs.sh <your-processed-data-bucket>
```

## Phase 1 weather data pipeline (local-first)

```bash
cd backend
uv sync --dev
uv run python scripts/run_pipeline.py --start-year 2021 --end-year 2026
```

Quick smoke test (small subset):

```bash
cd backend
uv run python scripts/run_pipeline.py \
  --start-year 2026 --end-year 2026 \
  --max-lightning-days 5 \
  --max-cloud-stations 10
```

The pipeline downloads raw SMHI data and writes local aggregates used by
`POST /api/metrics/point`.

> Note: first-time run downloads many files and can take time.

---

## Methodology: calculations and measurements

This section describes exactly how metrics are calculated.

### 1) Input datasets

### 1.0 Exact SMHI endpoints used for frontend numbers

The values shown in frontend charts are derived from these endpoints:

- Lightning API root:
  - `https://opendata-download-lightning.smhi.se/api/version/latest.json`
- Lightning per-year listing:
  - `https://opendata-download-lightning.smhi.se/api/version/latest/year/{year}.json`
- Lightning per-month listing:
  - `https://opendata-download-lightning.smhi.se/api/version/latest/year/{year}/month/{month}.json`
- Lightning daily CSV (raw event rows):
  - `https://opendata-download-lightning.smhi.se/api/version/latest/year/{year}/month/{month}/day/{day}/data.csv`

- Cloud parameter metadata (station list for parameter 16):
  - `https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16.json`
- Cloud station corrected archive CSV:
  - `https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16/station/{station_id}/period/corrected-archive/data.csv`
- Cloud station recent months CSV:
  - `https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16/station/{station_id}/period/latest-months/data.csv`

Frontend chart numbers are returned by backend endpoint:
- `POST /api/metrics/point`

The backend endpoint reads precomputed local files under:
- `backend/data/processed/`

### 1.1 Data lineage (chart field -> processed source -> raw source)

| Frontend chart field | Backend response path | Processed file(s) | Raw source endpoint(s) |
|---|---|---|---|
| Day: lightning count | `daily.days[].lightning_count` | `lightning_h3_r7_daily.jsonl` | Lightning daily CSV: `/year/{y}/month/{m}/day/{d}/data.csv` |
| Day: cloud mean % | `daily.days[].cloud_mean_pct` | `cloud_station_daily.jsonl` | Cloud station CSVs: `corrected-archive/data.csv`, `latest-months/data.csv` |
| Month: lightning count | `monthly.months[].lightning_count` | `lightning_h3_r7_monthly.json` | Derived from lightning daily CSV rows |
| Month: lightning probability | `monthly.months[].lightning_probability` | `lightning_h3_r7_monthly.json` | Derived from lightning daily CSV rows |
| Month: cloud mean % | `monthly.months[].cloud_mean_pct` | `cloud_station_monthly.json` | Derived from merged cloud station CSV rows |
| Year: lightning count | `yearly.years[].lightning_count` | `lightning_h3_r7_yearly.json` | Derived from lightning daily CSV rows |
| Year: lightning probability | `yearly.years[].lightning_probability` | `lightning_h3_r7_yearly.json` | Derived from lightning daily CSV rows |
| Year: cloud mean % | `yearly.years[].cloud_mean_pct` | `cloud_station_yearly.json` | Derived from merged cloud station CSV rows |
| Nearest station label/distance | `cloud_station.*` | `station_index.json` | Parameter-16 station metadata: `/parameter/16.json` |
| Point H3 index | `point.h3_r7` | computed at request time | H3 transform of selected `(lat,lon)` |

Notes:
- Lightning metrics are spatially aggregated by **H3 resolution 7**.
- Cloud metrics are **station-based** and mapped via nearest station selection.
- `latest-months` is merged to extend recency (including 2026), while
  `corrected-archive` remains preferred when both provide the same timestamp.

#### Lightning (SMHI lightning archive)
- Source: daily CSV files (2021–2026)
- Each row is one lightning event with timestamp + lat/lon.

#### Cloud cover (SMHI metobs parameter 16)
- Parameter 16 = total cloud amount (%).
- Two station feeds are merged:
  1. `corrected-archive` (historical baseline)
  2. `latest-months` (recent updates, includes 2026 coverage)

### 2) Spatial model (H3 resolution 7)

For lightning, every strike point `(lat, lon)` is transformed into one
**H3 cell ID at resolution 7**.

Why:
- Gives stable, indexed spatial buckets.
- Enables fast point lookup by mapping selected point to the same H3 cell.

How:
- Backend uses `h3.latlng_to_cell(lat, lon, 7)`.
- That cell ID is the key for all lightning day/month/year aggregates.

### 3) Lightning metrics formulas

For each H3 r7 cell:

- **Daily strike count**
  - `strike_count(day) = number of lightning rows in that cell on that date`

- **Monthly strike count**
  - `strike_count(month) = sum of daily strike_count for month`

- **Monthly days_with_strike**
  - count of days in month where `daily strike_count > 0`

- **Monthly lightning_probability**
  - `days_with_strike / days_in_month`

- **Yearly strike count**
  - `sum of daily strike_count over year`

- **Yearly lightning_probability**
  - `days_with_strike_in_year / days_in_year`

### 4) Cloud metrics formulas

Cloud is station-based (not H3).

#### 4.1 Data quality filtering
- Keep only rows with quality code `G` or `Y`.
- Ignore missing/non-numeric values.
- Filter to date >= `2021-01-01`.

#### 4.2 Merge corrected + latest-months
For each station and timestamp `(date,time)`:
- Prefer `corrected-archive` value over `latest-months` value.
- If same source priority, prefer quality `G` over `Y`.

This avoids duplicates while allowing 2026 recency.

#### 4.3 Aggregation
For each station:
- **Daily cloud mean %** = arithmetic mean of hourly values that day.
- **Monthly cloud mean %** = weighted mean over all daily samples.
- **Yearly cloud mean %** = weighted mean over all daily samples.

`n_samples` is preserved at each level for traceability.

### 5) Point query logic (`POST /api/metrics/point`)

Given `(lat, lon, year, month)`:

1. Validate point is inside Sweden bounds (phase-1 safety bound).
2. Convert point to H3 r7 cell.
3. Select nearest cloud station with priority:
   - nearest station with cloud data for selected year/month
   - else nearest station with any cloud data in aggregates
   - else nearest station overall
4. Build response:
   - daily series for selected month
   - monthly series for selected year
   - yearly series from 2021 to selected/current year

### 6) Why day/month can be empty while yearly has values

This is expected when:
- selected month has no events in that H3 cell, or
- selected year/month has no cloud samples for nearby stations,
while prior years still contain data.

The UI now shows warnings for these cases.

### 7) Aggregate validation

`scripts/validate_aggregates.py` checks:
- lightning daily -> monthly/yearly consistency (exact)
- cloud daily -> monthly/yearly consistency (within tolerance)

Run:

```bash
make validate-aggregates
```

## Local run (split dev mode)

### Backend

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Then open: http://localhost:5173

Vite proxy is preconfigured (`/api` -> `http://localhost:8000`).

In the UI:

1. Click a point on the map in Sweden
2. Pick year/month
3. Inspect day/month/year charts

## Local run (single container mode)

```bash
docker build -t weather-eval:local .
docker run --rm -p 8080:8080 \
  -e WEATHER_EVAL_FIRESTORE_PROJECT_ID=<your-project-id> \
  weather-eval:local
```

Then open: http://localhost:8080

## Firestore seed example

Create document:
- Collection: `app`
- Document: `hello`
- Field: `message` (string)

Example value:
`Hello from Firestore 🎉`

or seed it via script:

```bash
cd backend
WEATHER_EVAL_FIRESTORE_PROJECT_ID=<your-project-id> uv run python scripts/seed_firestore.py
```

## Terraform flow

### 1) Bootstrap state bucket

```bash
cd infra/bootstrap
terraform init
terraform apply \
  -var='project_id=<your-project-id>' \
  -var='state_bucket_name=<globally-unique-bucket-name>'
```

### 2) Main infra

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
# required: processed_data_bucket_name must be globally unique

terraform init \
  -backend-config="bucket=<your-state-bucket>" \
  -backend-config="prefix=weather-eval"
terraform apply
```

## Required GitHub secrets for deploy workflow

- `GCP_SA_KEY` (service account JSON key)

## Required GitHub repository variables for deploy workflow

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GAR_REPOSITORY`
- `CLOUD_RUN_SERVICE`
- `WEATHER_DATA_BUCKET` (Terraform `processed_data_bucket` output)
- `WEATHER_DATA_PREFIX` (optional; defaults to `processed/current`)

## Deployment mode choices

- **Option A (current):** GitHub Actions builds/pushes image and runs `gcloud run deploy`.
  - Simple and fast.
  - Infra stays in Terraform, app revision rollout is done by CI.

- **Option B:** Terraform-only deploys (image value updated in Terraform and applied).
  - Stronger single source of truth.
  - Slightly slower/more operational overhead.

## Cost guardrails

- Cloud Run is pinned to low-cost defaults in Terraform:
  - `min instances = 0`
  - `max instances = 1`
  - `memory = 2Gi`
  - `concurrency = 1`
- Firestore usage is tiny in this starter (single document read).
- Artifact Registry free tier includes a small monthly storage allowance.
- Terraform state bucket default location is `US-CENTRAL1` (to align with Cloud Storage always-free regional locations).

> Note: Cloud Run free tier depends on actual monthly vCPU-seconds, GiB-seconds,
> requests, region, and egress. This configuration minimizes idle cost
> (`min instances = 0`) and caps scale (`max instances = 1`) but does not
> guarantee zero cost under all traffic patterns.

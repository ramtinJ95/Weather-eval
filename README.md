# weather-eval

Monorepo starter for:
- React + TypeScript frontend (`frontend/`)
- FastAPI backend (`backend/`)
- single Docker image serving both
- Terraform on GCP (`infra/`)
- GitHub Actions CI/CD (`.github/workflows/`)

## What works now

- `/api/health` returns backend health
- `/api/hello` reads from Firestore and falls back to default text
- `/api/metrics/point` returns cloud/lightning metrics for a selected lat/lon
- frontend includes a map-click workflow + day/month/year charts
- Docker image builds frontend and serves it from FastAPI

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

> Note: first-time download can take a while because it fetches many files.

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

terraform init \
  -backend-config="bucket=<your-state-bucket>" \
  -backend-config="prefix=weather-eval"
terraform apply
```

## Required GitHub secrets for deploy workflow

- `GCP_SA_KEY` (service account JSON key)
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GAR_REPOSITORY`
- `CLOUD_RUN_SERVICE`

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
  - `memory = 256Mi`
- Firestore usage is tiny in this starter (single document read).
- Artifact Registry free tier includes a small monthly storage allowance.
- Terraform state bucket default location is `US-CENTRAL1` (to align with Cloud Storage always-free regional locations).

> Note: With app region `europe-west1`, some traffic/storage patterns can still create small charges depending on usage.

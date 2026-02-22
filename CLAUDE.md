# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
make run               # Start backend (:8000) + frontend (:5173) concurrently
make backend-dev       # Backend only (FastAPI with hot reload)
make frontend-dev      # Frontend only (Vite dev server)
```

### Testing & Linting
```bash
make test              # Backend pytest
make lint              # Backend (ruff check + ruff format --check + ty check) + Frontend (eslint)

# Run a single backend test
cd backend && uv run pytest tests/test_metrics.py -k test_name

# Individual lint tools
cd backend && uv run ruff check .
cd backend && uv run ruff format --check .
cd backend && uv tool run ty check app
cd frontend && npm run lint
```

### Data Pipeline
```bash
make pipeline          # Full pipeline (2023-2026, takes a while on first run)
make pipeline-smoke    # Quick subset (2026 only, 5 lightning days, 10 cloud stations)
```

### Docker
```bash
make docker-build      # Build single container image
```

## Architecture

**Monorepo** with three independent sub-projects sharing a single Docker image and root Makefile:

- `backend/` — Python 3.12+ / FastAPI, managed by **uv** (`pyproject.toml` + `uv.lock`)
- `frontend/` — React 18 + TypeScript + Vite, managed by **npm** (`package.json`)
- `infra/` — Terraform for GCP (Cloud Run, Firestore, Artifact Registry)

### Data Flow

1. **Pipeline scripts** (`backend/scripts/`) download raw SMHI data (lightning CSVs, cloud station CSVs) into `backend/data/raw/`, then build aggregates into `backend/data/processed/` (daily JSONL, monthly/yearly JSON).
2. **MetricsStore** (`backend/app/weather_metrics.py`) lazily loads processed aggregates into memory on first request, caching via `@lru_cache`.
3. **POST /api/metrics/point** accepts `{lat, lon, year, month}`, converts coordinates to an H3 resolution-7 cell for lightning and finds the nearest cloud station via Haversine distance, then returns daily/monthly/yearly metrics.
4. **Frontend** (`frontend/src/App.tsx`) renders a Leaflet map of Sweden. Click sets coordinates, then fetches metrics and displays day/month/year charts via Recharts.

### Spatial Indexing

Lightning data uses **H3 hexagonal cells at resolution 7** (~5km). Cloud data is tied to SMHI observation stations; the API finds the nearest station to the clicked point.

### Deployment

Multi-stage Dockerfile: Node builds frontend, Python serves both frontend (as static files via FastAPI) and API. Deployed to GCP Cloud Run via GitHub Actions CI/CD.

## Conventions

- **Backend linting**: ruff (rules: E, F, I, UP, B, A, C4, SIM), line length 100, target Python 3.12. Type checking with `ty`.
- **Frontend linting**: eslint with typescript-eslint, react-hooks, and react-refresh plugins.
- **Vite proxy**: `/api` requests from the frontend dev server proxy to `http://localhost:8000`.
- **Environment config**: Pydantic Settings with `WEATHER_EVAL_` prefix (see `backend/.env.example`).
- **Sweden bounds validation**: lat 55-69.5, lon 10.5-24.5.

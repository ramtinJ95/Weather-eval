.PHONY: backend-dev frontend-dev run test lint docker-build pipeline pipeline-smoke fetch-lightning refresh-cloud upload-processed validate-aggregates

backend-dev:
	cd backend && uv sync --dev && uv run uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm ci && npm run dev

run:
	@echo "Starting backend (:8000) + frontend (:5173). Press Ctrl+C to stop both."
	@set -e; \
	trap 'kill $$BACKEND_PID $$FRONTEND_PID 2>/dev/null || true' INT TERM EXIT; \
	(cd backend && uv sync --dev && uv run uvicorn app.main:app --reload --port 8000) & BACKEND_PID=$$!; \
	(cd frontend && if [ ! -d node_modules ]; then npm ci; fi; npm run dev -- --host 0.0.0.0 --port 5173) & FRONTEND_PID=$$!; \
	wait $$BACKEND_PID $$FRONTEND_PID

test:
	cd backend && uv sync --dev && uv run pytest

lint:
	cd backend && uv sync --dev && uv run ruff check . && uv run ruff format --check . && uv tool run ty check app
	cd frontend && npm ci && npm run lint

docker-build:
	docker build -t weather-eval:local .

pipeline:
	cd backend && uv sync --dev && uv run python scripts/run_pipeline.py --start-year 2023 --end-year 2026

pipeline-smoke:
	cd backend && uv sync --dev && uv run python scripts/run_pipeline.py --start-year 2026 --end-year 2026 --max-lightning-days 5 --max-cloud-stations 10

fetch-lightning:
	cd backend && uv sync --dev && uv run python scripts/fetch_lightning_raw.py --start-year 2023 --end-year 2026

refresh-cloud:
	cd backend && uv sync --dev && uv run python scripts/fetch_cloud_raw.py && uv run python scripts/build_cloud_aggregates.py --start-date 2023-01-01

upload-processed:
	@if [ -z "$$WEATHER_DATA_BUCKET" ]; then \
		echo "Set WEATHER_DATA_BUCKET first, e.g. WEATHER_DATA_BUCKET=my-bucket make upload-processed"; \
		exit 1; \
	fi
	./scripts/upload_processed_to_gcs.sh $$WEATHER_DATA_BUCKET

validate-aggregates:
	cd backend && uv sync --dev && uv run python scripts/validate_aggregates.py

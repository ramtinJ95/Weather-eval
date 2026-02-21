.PHONY: backend-dev frontend-dev test lint docker-build

backend-dev:
	cd backend && uv sync --dev && uv run uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm ci && npm run dev

test:
	cd backend && uv sync --dev && uv run pytest

lint:
	cd backend && uv sync --dev && uv run ruff check . && uv run ruff format --check . && uv tool run ty check app
	cd frontend && npm ci && npm run lint

docker-build:
	docker build -t weather-eval:local .

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import PointMetricsRequest, PointMetricsResponse
from app.weather_metrics import MetricsStore

app = FastAPI(
    title=settings.app_name,
    middleware=[
        Middleware(
            cast(Any, CORSMiddleware),
            allow_origins=[settings.frontend_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache
def get_metrics_store() -> MetricsStore:
    return MetricsStore.from_processed_dir(
        settings.processed_data_dir,
        start_year=settings.weather_start_year,
        h3_resolution=settings.weather_h3_resolution,
        bounds=(
            settings.sweden_min_lat,
            settings.sweden_max_lat,
            settings.sweden_min_lon,
            settings.sweden_max_lon,
        ),
        idw_power=settings.idw_power,
        idw_max_neighbors=settings.idw_max_neighbors,
        idw_max_distance_km=settings.idw_max_distance_km,
    )


@app.post("/api/metrics/point", response_model=PointMetricsResponse)
def metrics_for_point(payload: PointMetricsRequest) -> PointMetricsResponse:
    store = get_metrics_store()
    if not store.is_point_in_bounds(payload.lat, payload.lon):
        raise HTTPException(
            status_code=400,
            detail="Selected point is outside Sweden bounds for this phase.",
        )

    return store.query(lat=payload.lat, lon=payload.lon, year=payload.year, month=payload.month)


frontend_dist = Path(__file__).resolve().parents[2] / "frontend_dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:  # noqa: ARG001
        return FileResponse(frontend_dist / "index.html")

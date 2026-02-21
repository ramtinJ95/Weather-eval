from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import read_hello_message
from app.schemas import HelloResponse

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


@app.get("/api/hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    message, source = read_hello_message()
    return HelloResponse(message=message, source=source)


frontend_dist = Path(__file__).resolve().parents[2] / "frontend_dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:  # noqa: ARG001
        return FileResponse(frontend_dist / "index.html")

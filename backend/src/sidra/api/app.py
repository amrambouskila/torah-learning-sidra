"""The FastAPI application.

Nothing here is stored: ``/api/today`` recomputes every track's debt from the ledger and the
catalog on each request, so what the screen shows can never drift from what is recorded.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sidra.api.routers import (
    alignment,
    chavrusas,
    maintenance,
    pace,
    roadmap,
    sequence,
    stats,
    tags,
    today,
    track_writes,
    tracks,
)
from sidra.config import get_settings
from sidra.db.engine import create_engine, create_session_factory

TITLE = "Torah Learning Sidra"
VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(get_settings().database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=TITLE, version=VERSION, lifespan=lifespan)
    # A desktop-only app served from one origin; the allowlist is explicit rather than "*" because
    # a wildcard would still be wrong the day anything here reads an auth header.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in get_settings().cors_origins.split(",") if origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    for module in (
        today,
        tracks,
        track_writes,
        roadmap,
        chavrusas,
        tags,
        alignment,
        pace,
        stats,
        sequence,
        maintenance,
    ):
        app.include_router(module.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app

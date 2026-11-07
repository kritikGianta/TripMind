"""Application factory. Run with: uvicorn app.main:create_app --factory"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app import __version__
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.features import load_feature_flags
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.ingestion.router import admin_router as imports_admin_router
from app.modules.ingestion.router import public_router as datasets_router
from app.modules.meta.router import router as meta_router

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    flags = load_feature_flags(settings)  # validates flags at start-up (fail fast)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info(
            "api_started",
            environment=settings.environment,
            version=__version__,
            features=flags.as_dict(),
        )
        yield
        log.info("api_stopped")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["content-type", "x-request-id", "idempotency-key", "x-requested-with"],
        )
    register_exception_handlers(app)

    app.include_router(meta_router, prefix=settings.api_prefix)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(datasets_router, prefix=settings.api_prefix)
    app.include_router(imports_admin_router, prefix=settings.api_prefix)

    # Served on the API's own port only; the web proxy forwards /api/* and never /metrics.
    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vaultlog.presentation.api.v1.health import router as health_router
from vaultlog.shared.config import get_settings
from vaultlog.shared.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)

    logger = structlog.get_logger()
    logger.info(
        "application.starting",
        service=settings.service_name,
        environment=settings.environment,
    )

    yield

    logger.info("application.stopping", service=settings.service_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="VaultLog API",
        version="0.1.0",
        description="Security-first multi-tenant vault and secret management API.",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )

    allowed_origins = [
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.include_router(health_router, prefix="/api/v1")

    return app


app = create_app()

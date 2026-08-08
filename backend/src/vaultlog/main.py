from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vaultlog.infrastructure.database.engine import build_engine, build_session_factory
from vaultlog.presentation.api.v1.auth import router as auth_router
from vaultlog.presentation.api.v1.health import router as health_router
from vaultlog.presentation.exception_handlers import register_exception_handlers
from vaultlog.shared.config import get_settings
from vaultlog.shared.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)

    logger = structlog.get_logger()

    app_engine = build_engine(settings.database_url)
    identity_engine = build_engine(settings.migration_database_url)
    app.state.session_factory = build_session_factory(app_engine)
    app.state.identity_session_factory = build_session_factory(identity_engine)

    logger.info(
        "application.starting",
        service=settings.service_name,
        environment=settings.environment,
    )

    yield

    await identity_engine.dispose()
    await app_engine.dispose()
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
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Step-Up-Token"],
    )

    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")

    return app


app = create_app()

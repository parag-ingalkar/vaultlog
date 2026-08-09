from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vaultlog.infrastructure.database.engine import build_engine, build_session_factory
from vaultlog.infrastructure.security.rate_limit import RedisRateLimiter
from vaultlog.presentation.api.v1.audit import router as audit_router
from vaultlog.presentation.api.v1.auth import router as auth_router
from vaultlog.presentation.api.v1.health import router as health_router
from vaultlog.presentation.api.v1.invitations import router as invitations_router
from vaultlog.presentation.api.v1.members import router as members_router
from vaultlog.presentation.api.v1.organization import router as organization_router
from vaultlog.presentation.api.v1.secrets import router as secrets_router
from vaultlog.presentation.api.v1.vaults import router as vaults_router
from vaultlog.presentation.dependencies import require_mfa_if_owner
from vaultlog.presentation.exception_handlers import register_exception_handlers
from vaultlog.presentation.middleware import (
    OriginCheckMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from vaultlog.shared.config import get_settings
from vaultlog.shared.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)

    logger = structlog.get_logger()

    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    app.state.redis_client = redis_client
    app.state.rate_limiter = RedisRateLimiter(redis_client)

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

    await redis_client.aclose()
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
    app.add_middleware(OriginCheckMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(
        vaults_router,
        prefix="/api/v1",
        dependencies=[Depends(require_mfa_if_owner)],
    )
    app.include_router(
        secrets_router,
        prefix="/api/v1",
        dependencies=[Depends(require_mfa_if_owner)],
    )
    app.include_router(
        audit_router,
        prefix="/api/v1",
        dependencies=[Depends(require_mfa_if_owner)],
    )
    app.include_router(invitations_router, prefix="/api/v1")
    app.include_router(members_router, prefix="/api/v1")
    app.include_router(organization_router, prefix="/api/v1")

    return app


app = create_app()

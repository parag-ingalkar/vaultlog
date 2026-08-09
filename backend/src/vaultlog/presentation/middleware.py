from __future__ import annotations

import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from vaultlog.presentation.errors import error_body, request_id_from
from vaultlog.shared.config import Settings, get_settings

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request_id = request_id[:64]
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "method", "path")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """CSRF defense-in-depth for cookie-authenticated mutation endpoints."""

    PROTECTED_PREFIXES = ("/api/v1/auth/refresh", "/api/v1/auth/logout")

    def __init__(self, app: Any, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and any(
            request.url.path.startswith(prefix) for prefix in self.PROTECTED_PREFIXES
        ):
            origin = request.headers.get("origin")
            allowed = {
                item.strip() for item in self._settings.cors_origins.split(",") if item.strip()
            }
            if origin is not None and origin not in allowed:
                return JSONResponse(
                    status_code=403,
                    content=error_body(
                        "csrf_origin_mismatch",
                        "Forbidden",
                        request_id_from(request),
                    ),
                )
        return await call_next(request)

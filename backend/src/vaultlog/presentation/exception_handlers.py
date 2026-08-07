from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    PasswordPolicyError,
    RegistrationConflictError,
    TokenValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PasswordPolicyError)
    async def password_policy_error(
        request: Request,
        exc: PasswordPolicyError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc) or "Invalid password"},
        )

    @app.exception_handler(RegistrationConflictError)
    async def registration_conflict_error(
        request: Request,
        exc: RegistrationConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc) or "Registration failed"},
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error(
        request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc) or "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(TokenValidationError)
    async def token_validation_error(
        request: Request,
        exc: TokenValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )

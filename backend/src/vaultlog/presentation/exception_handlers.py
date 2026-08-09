from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    MfaEnrollmentError,
    MfaVerificationError,
    PasswordPolicyError,
    RegistrationConflictError,
    StepUpRequiredError,
    TokenValidationError,
)
from vaultlog.domain.secrets.exceptions import (
    CryptoError,
    NoActiveKeyError,
    SecretConflictError,
    TenantKeyProvisionError,
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

    @app.exception_handler(MfaEnrollmentError)
    async def mfa_enrollment_error(
        request: Request,
        exc: MfaEnrollmentError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc) or "Invalid code"},
        )

    @app.exception_handler(MfaVerificationError)
    async def mfa_verification_error(
        request: Request,
        exc: MfaVerificationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc) or "Invalid code"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(StepUpRequiredError)
    async def step_up_required_error(
        request: Request,
        exc: StepUpRequiredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc) or "Step-up authentication required"},
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_error(
        request: Request,
        exc: ForbiddenError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Access denied"},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error(
        request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not found"},
        )

    @app.exception_handler(SecretConflictError)
    async def secret_conflict_error(
        request: Request,
        exc: SecretConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc) or "Conflict"},
        )

    @app.exception_handler(NoActiveKeyError)
    async def no_active_key_error(
        request: Request,
        exc: NoActiveKeyError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Encryption key unavailable"},
        )

    @app.exception_handler(CryptoError)
    async def crypto_error(
        request: Request,
        exc: CryptoError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Cryptographic operation failed"},
        )

    @app.exception_handler(TenantKeyProvisionError)
    async def tenant_key_provision_error(
        request: Request,
        exc: TenantKeyProvisionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc) or "Tenant encryption setup failed"},
        )

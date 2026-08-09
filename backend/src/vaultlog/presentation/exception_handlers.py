from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.audit.exceptions import AuditMetadataError, UnknownAuditActionError
from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    MfaEnrollmentError,
    MfaVerificationError,
    PasswordPolicyError,
    RegistrationConflictError,
    ServiceUnavailableError,
    StepUpRequiredError,
    TokenValidationError,
)
from vaultlog.domain.secrets.exceptions import (
    CryptoError,
    NoActiveKeyError,
    SecretConflictError,
    TenantKeyProvisionError,
)
from vaultlog.presentation.errors import error_body, http_exception_message, request_id_from

logger = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                f"http_{exc.status_code}",
                http_exception_message(exc.detail),
                request_id_from(request),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        fields = [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_failed",
                    "fields": fields,
                    "request_id": request_id_from(request),
                }
            },
        )

    @app.exception_handler(PasswordPolicyError)
    async def password_policy_error(
        request: Request,
        exc: PasswordPolicyError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body(
                "password_policy_violation",
                str(exc) or "Invalid password",
                request_id_from(request),
            ),
        )

    @app.exception_handler(RegistrationConflictError)
    async def registration_conflict_error(
        request: Request,
        exc: RegistrationConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body(
                "registration_conflict",
                str(exc) or "Registration failed",
                request_id_from(request),
            ),
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error(
        request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_body(
                "authentication_failed",
                str(exc) or "Not authenticated",
                request_id_from(request),
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(TokenValidationError)
    async def token_validation_error(
        request: Request,
        exc: TokenValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_body(
                "authentication_failed",
                "Not authenticated",
                request_id_from(request),
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(MfaEnrollmentError)
    async def mfa_enrollment_error(
        request: Request,
        exc: MfaEnrollmentError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body(
                "mfa_enrollment_failed",
                str(exc) or "Invalid code",
                request_id_from(request),
            ),
        )

    @app.exception_handler(MfaVerificationError)
    async def mfa_verification_error(
        request: Request,
        exc: MfaVerificationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_body(
                "mfa_verification_failed",
                str(exc) or "Invalid code",
                request_id_from(request),
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(StepUpRequiredError)
    async def step_up_required_error(
        request: Request,
        exc: StepUpRequiredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_body(
                "step_up_required",
                str(exc) or "Step-up authentication required",
                request_id_from(request),
            ),
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_error(
        request: Request,
        exc: ServiceUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_body(
                "service_unavailable",
                str(exc) or "Service unavailable",
                request_id_from(request),
            ),
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_error(
        request: Request,
        exc: ForbiddenError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_body(
                "forbidden",
                "Access denied",
                request_id_from(request),
            ),
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error(
        request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_body(
                "not_found",
                "Not found",
                request_id_from(request),
            ),
        )

    @app.exception_handler(SecretConflictError)
    async def secret_conflict_error(
        request: Request,
        exc: SecretConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body(
                "secret_conflict",
                str(exc) or "Conflict",
                request_id_from(request),
            ),
        )

    @app.exception_handler(NoActiveKeyError)
    async def no_active_key_error(
        request: Request,
        exc: NoActiveKeyError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(
                "encryption_key_unavailable",
                "Encryption key unavailable",
                request_id_from(request),
            ),
        )

    @app.exception_handler(CryptoError)
    async def crypto_error(
        request: Request,
        exc: CryptoError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(
                "cryptographic_error",
                "Cryptographic operation failed",
                request_id_from(request),
            ),
        )

    @app.exception_handler(TenantKeyProvisionError)
    async def tenant_key_provision_error(
        request: Request,
        exc: TenantKeyProvisionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(
                "tenant_key_provision_failed",
                str(exc) or "Tenant encryption setup failed",
                request_id_from(request),
            ),
        )

    @app.exception_handler(AuditMetadataError)
    @app.exception_handler(UnknownAuditActionError)
    async def audit_validation_error(
        request: Request,
        exc: AuditMetadataError | UnknownAuditActionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body(
                "audit_validation_failed",
                str(exc) or "Invalid audit event",
                request_id_from(request),
            ),
        )

    def _internal_error_response(request: Request, exc: BaseException) -> JSONResponse:
        log_exc: BaseException = exc
        if isinstance(exc, ExceptionGroup):
            log_exc = exc.exceptions[0] if exc.exceptions else exc
        logger.error(
            "unhandled_exception",
            exc_type=type(log_exc).__name__,
            path=request.url.path,
            request_id=request_id_from(request),
            exc_info=log_exc,
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(
                "internal_error",
                "An internal error occurred",
                request_id_from(request),
            ),
        )
        request_id = request_id_from(request)
        if request_id is not None:
            response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ExceptionGroup)
    async def exception_group_error(
        request: Request,
        exc: ExceptionGroup,
    ) -> JSONResponse:
        # BaseHTTPMiddleware wraps route errors in ExceptionGroup; it is not a
        # subclass of Exception, so this handler is required alongside the one below.
        return _internal_error_response(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        return _internal_error_response(request, exc)

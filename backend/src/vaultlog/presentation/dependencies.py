from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.identity.use_cases import (
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
)
from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.domain.identity.exceptions import TokenValidationError
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    session_id: UUID
    amr: tuple[str, ...]


def get_app_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)


def get_identity_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(
        async_sessionmaker[AsyncSession],
        request.app.state.identity_session_factory,
    )


@lru_cache
def get_password_hasher() -> Argon2Hasher:
    return Argon2Hasher()


@lru_cache
def get_token_service() -> TokenService:
    return TokenService(get_settings())


def get_identity_uow_factory(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_identity_session_factory),
) -> Callable[[], IdentityUnitOfWork]:
    def factory() -> IdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(session_factory)

    return factory


def get_register_user(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> RegisterUser:
    return RegisterUser(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_login_user(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> LoginUser:
    return LoginUser(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_refresh_tokens(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> RefreshTokens:
    return RefreshTokens(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_logout_session(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> LogoutSession:
    return LogoutSession(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tokens: TokenService = Depends(get_token_service),
) -> Principal:
    if credentials is None:
        raise _unauthorized
    try:
        claims = tokens.verify_access_token(credentials.credentials)
    except TokenValidationError:
        raise _unauthorized from None
    return Principal(
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        session_id=claims.session_id,
        amr=claims.amr,
    )


def get_tenant_uow(
    principal: Principal = Depends(current_principal),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> SqlAlchemyUnitOfWork:
    context = TenantContext(tenant_id=principal.tenant_id)
    return SqlAlchemyUnitOfWork(session_factory, context)

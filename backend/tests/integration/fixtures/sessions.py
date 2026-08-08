"""Per-test database reset and session factories."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.identity.use_cases import (
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
)
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings


@pytest.fixture()
def scoped_session(app_engine):
    factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async def _open(tenant_id):
        session = factory()
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        return session

    return _open


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def identity_session_factory(owner_engine):
    return async_sessionmaker(owner_engine, expire_on_commit=False)


@pytest.fixture()
def identity_uow_factory(identity_session_factory):
    def factory() -> SqlAlchemyIdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(identity_session_factory)

    return factory


@pytest.fixture()
def passwords() -> Argon2Hasher:
    return Argon2Hasher()


@pytest.fixture()
def tokens() -> TokenService:
    return TokenService(get_settings())


@pytest.fixture()
def register_user(identity_uow_factory, passwords, tokens) -> RegisterUser:
    settings = get_settings()
    return RegisterUser(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def login_user(identity_uow_factory, passwords, tokens) -> LoginUser:
    settings = get_settings()
    return LoginUser(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def refresh_tokens(identity_uow_factory, passwords, tokens) -> RefreshTokens:
    settings = get_settings()
    return RefreshTokens(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def logout_session(identity_uow_factory, passwords, tokens) -> LogoutSession:
    settings = get_settings()
    return LogoutSession(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )

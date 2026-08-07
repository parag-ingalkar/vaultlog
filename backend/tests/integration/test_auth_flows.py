from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from vaultlog.application.identity.use_cases import (
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
)
from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings

pytestmark = pytest.mark.asyncio(loop_scope="module")

PASSWORD = "correct horse battery"
settings = get_settings()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
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
    return TokenService(settings)


@pytest.fixture()
def register_user(identity_uow_factory, passwords, tokens) -> RegisterUser:
    return RegisterUser(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def login_user(identity_uow_factory, passwords, tokens) -> LoginUser:
    return LoginUser(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def refresh_tokens(identity_uow_factory, passwords, tokens) -> RefreshTokens:
    return RefreshTokens(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


@pytest.fixture()
def logout_session(identity_uow_factory, passwords, tokens) -> LogoutSession:
    return LogoutSession(
        identity_uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
    )


def _unique_email(prefix: str = "ada") -> str:
    import uuid

    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


async def test_register_then_login_returns_token_pair(register_user, login_user) -> None:
    email = _unique_email()
    await register_user.execute(email, PASSWORD, "Acme")
    pair = await login_user.execute(email, PASSWORD, "pytest")
    assert pair.access_token
    assert pair.refresh_token
    claims = TokenService(settings).verify_access_token(pair.access_token)
    assert claims.user_id
    assert claims.tenant_id
    assert claims.session_id


async def test_wrong_password_gives_same_error_as_unknown_email(
    register_user,
    login_user,
) -> None:
    email = _unique_email()
    await register_user.execute(email, PASSWORD, "Acme")
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await login_user.execute(email, "wrong password!!", None)
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await login_user.execute("nobody@example.com", "any password 12", None)


async def test_refresh_rotation_consumes_old_token(
    register_user,
    login_user,
    refresh_tokens,
) -> None:
    email = _unique_email("rotate")
    await register_user.execute(email, PASSWORD, "Acme")
    pair1 = await login_user.execute(email, PASSWORD, "pytest")
    pair2 = await refresh_tokens.execute(pair1.refresh_token)
    assert pair2.access_token and pair2.refresh_token
    assert pair2.refresh_token != pair1.refresh_token

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair1.refresh_token)


async def test_refresh_reuse_revokes_session_family(
    register_user,
    login_user,
    refresh_tokens,
) -> None:
    email = _unique_email("reuse")
    await register_user.execute(email, PASSWORD, "Acme")
    pair1 = await login_user.execute(email, PASSWORD, "pytest")
    pair2 = await refresh_tokens.execute(pair1.refresh_token)

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair1.refresh_token)

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair2.refresh_token)


async def test_logout_revokes_session(
    register_user,
    login_user,
    logout_session,
    refresh_tokens,
) -> None:
    email = _unique_email("logout")
    await register_user.execute(email, PASSWORD, "Acme")
    pair = await login_user.execute(email, PASSWORD, "pytest")
    await logout_session.execute(pair.refresh_token)
    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair.refresh_token)

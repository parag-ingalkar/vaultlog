"""Per-test database reset and session factories."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.identity.use_cases import (
    CompleteMfaLogin,
    ConfirmTotpEnrollment,
    DisableMfa,
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
    StartTotpEnrollment,
    StepUpVerify,
)
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.security.mfa import PyotpTotpVerifier
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.seed_encryption import AesGcmSeedEncryptor
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
def seed_encryptor() -> AesGcmSeedEncryptor:
    return AesGcmSeedEncryptor(get_settings())


@pytest.fixture()
def totp_verifier() -> PyotpTotpVerifier:
    return PyotpTotpVerifier()


def _mfa_kwargs(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> dict:
    settings = get_settings()
    return {
        "uow_factory": identity_uow_factory,
        "seed_encryptor": seed_encryptor,
        "totp_verifier": totp_verifier,
        "tokens": tokens,
        "refresh_ttl_days": settings.refresh_token_ttl_days,
    }


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


@pytest.fixture()
def start_totp_enrollment(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> StartTotpEnrollment:
    kwargs = _mfa_kwargs(identity_uow_factory, seed_encryptor, totp_verifier, tokens)
    return StartTotpEnrollment(**kwargs)


@pytest.fixture()
def confirm_totp_enrollment(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> ConfirmTotpEnrollment:
    kwargs = _mfa_kwargs(identity_uow_factory, seed_encryptor, totp_verifier, tokens)
    return ConfirmTotpEnrollment(**kwargs)


@pytest.fixture()
def complete_mfa_login(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> CompleteMfaLogin:
    kwargs = _mfa_kwargs(identity_uow_factory, seed_encryptor, totp_verifier, tokens)
    return CompleteMfaLogin(**kwargs)


@pytest.fixture()
def step_up_verify(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> StepUpVerify:
    return StepUpVerify(**_mfa_kwargs(identity_uow_factory, seed_encryptor, totp_verifier, tokens))


@pytest.fixture()
def disable_mfa(
    identity_uow_factory,
    seed_encryptor,
    totp_verifier,
    tokens,
) -> DisableMfa:
    return DisableMfa(**_mfa_kwargs(identity_uow_factory, seed_encryptor, totp_verifier, tokens))

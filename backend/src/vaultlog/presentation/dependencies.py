from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.audit.use_cases import ListAuditEvents, RecordAccessDenial
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
from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.application.secrets.use_cases import (
    CreateSecret,
    DeleteSecret,
    ListSecrets,
    ProvisionTenantKey,
    RevealSecret,
    RotateSecret,
)
from vaultlog.application.vaults.use_cases import (
    CreateVault,
    DeleteVault,
    ListVaults,
    ManageGrant,
    UpdateVault,
)
from vaultlog.domain.audit.models import ActorContext
from vaultlog.domain.identity.exceptions import StepUpRequiredError, TokenValidationError
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from vaultlog.infrastructure.security.mfa import PyotpTotpVerifier
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.seed_encryption import AesGcmSeedEncryptor
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.infrastructure.security.vault_crypto import (
    AesGcmSecretEncryptor,
    LocalKEKProvider,
)
from vaultlog.shared.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


class StepUpPurpose(StrEnum):
    DELETE_VAULT = "step-up:delete-vault"
    DELETE_SECRET = "step-up:delete-secret"
    REMOVE_MEMBER = "step-up:remove-member"
    MANAGE_MFA = "step-up:manage-mfa"
    ROTATE_KEYS = "step-up:rotate-keys"


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    session_id: UUID
    amr: tuple[str, ...]

    def to_actor(self) -> ActorContext:
        return ActorContext(
            user_id=self.user_id,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
        )


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


@lru_cache
def get_seed_encryptor() -> AesGcmSeedEncryptor:
    return AesGcmSeedEncryptor(get_settings())


@lru_cache
def get_totp_verifier() -> PyotpTotpVerifier:
    return PyotpTotpVerifier()


@lru_cache
def get_secret_encryptor() -> AesGcmSecretEncryptor:
    return AesGcmSecretEncryptor()


@lru_cache
def get_kek_provider() -> LocalKEKProvider:
    return LocalKEKProvider(get_settings())


def get_identity_uow_factory(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_identity_session_factory),
) -> Callable[[], IdentityUnitOfWork]:
    def factory() -> IdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(session_factory)

    return factory


def get_tenant_uow_factory_for_tenant(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> Callable[[UUID], SqlAlchemyUnitOfWork]:
    def factory(tenant_id: UUID) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, TenantContext(tenant_id=tenant_id))

    return factory


def get_register_user(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    tenant_uow_factory: Callable[[UUID], SqlAlchemyUnitOfWork] = Depends(
        get_tenant_uow_factory_for_tenant
    ),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    settings: Settings = Depends(get_settings),
) -> RegisterUser:
    provision = ProvisionTenantKey(tenant_uow_factory, kek, encryptor)
    return RegisterUser(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
        provision_tenant_key=provision,
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


def get_start_totp_enrollment(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> StartTotpEnrollment:
    return StartTotpEnrollment(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_confirm_totp_enrollment(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> ConfirmTotpEnrollment:
    return ConfirmTotpEnrollment(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_complete_mfa_login(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> CompleteMfaLogin:
    return CompleteMfaLogin(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_step_up_verify(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> StepUpVerify:
    return StepUpVerify(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
    )


def get_disable_mfa(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
) -> DisableMfa:
    return DisableMfa(
        uow_factory,
        seed_encryptor,
        totp_verifier,
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


async def current_user(
    principal: Principal = Depends(current_principal),
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
) -> tuple[Principal, str]:
    async with uow_factory() as uow:
        user = await uow.users.get(principal.user_id)
        if user is None:
            raise _unauthorized
        return principal, user.email


def require_step_up(purpose: StepUpPurpose) -> Callable[..., Awaitable[Principal]]:
    async def dependency(
        request: Request,
        principal: Principal = Depends(current_principal),
        tokens: TokenService = Depends(get_token_service),
    ) -> Principal:
        token = request.headers.get("X-Step-Up-Token")
        if token is None:
            raise StepUpRequiredError("Step-up authentication required")
        try:
            tokens.verify_step_up_token(
                token,
                principal.user_id,
                principal.session_id,
                purpose.value,
            )
        except TokenValidationError:
            raise StepUpRequiredError("Step-up authentication required") from None
        return principal

    return dependency


def get_tenant_uow(
    principal: Principal = Depends(current_principal),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> SqlAlchemyUnitOfWork:
    context = TenantContext(tenant_id=principal.tenant_id)
    return SqlAlchemyUnitOfWork(session_factory, context)


def get_tenant_uow_factory(
    principal: Principal = Depends(current_principal),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> Callable[[], SqlAlchemyUnitOfWork]:
    context = TenantContext(tenant_id=principal.tenant_id)

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, context)

    return factory


def get_record_access_denial(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
) -> RecordAccessDenial:
    return RecordAccessDenial(uow_factory)


def get_create_vault(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> CreateVault:
    return CreateVault(uow_factory, record_denial)


def get_list_vaults(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
) -> ListVaults:
    return ListVaults(uow_factory)


def get_update_vault(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> UpdateVault:
    return UpdateVault(uow_factory, record_denial)


def get_delete_vault(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> DeleteVault:
    return DeleteVault(uow_factory, record_denial)


def get_manage_grant(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> ManageGrant:
    return ManageGrant(uow_factory, record_denial)


def get_create_secret(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> CreateSecret:
    return CreateSecret(uow_factory, kek, encryptor, record_denial)


def get_list_secrets(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
) -> ListSecrets:
    return ListSecrets(uow_factory, kek, encryptor)


def get_reveal_secret(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> RevealSecret:
    return RevealSecret(uow_factory, kek, encryptor, record_denial)


def get_rotate_secret(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> RotateSecret:
    return RotateSecret(uow_factory, kek, encryptor, record_denial)


def get_delete_secret(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> DeleteSecret:
    return DeleteSecret(uow_factory, kek, encryptor, record_denial)


def get_list_audit_events(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork] = Depends(get_tenant_uow_factory),
) -> ListAuditEvents:
    return ListAuditEvents(uow_factory)

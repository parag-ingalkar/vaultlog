from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Literal, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.audit.use_cases import ListAuditEvents, RecordAccessDenial
from vaultlog.application.identity.use_cases import (
    CompleteMfaLogin,
    ConfirmTotpEnrollment,
    DisableMfa,
    GetCurrentUser,
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
    StartTotpEnrollment,
    StepUpVerify,
)
from vaultlog.application.organizations.use_cases import (
    AcceptInvitation,
    CreateInvitation,
    GetOrganization,
    ListInvitations,
    ListMembers,
    PreviewInvitation,
    RemoveMember,
    RevokeInvitation,
)
from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
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
    GetVault,
    ListGrants,
    ListVaults,
    ManageGrant,
    UpdateVault,
)
from vaultlog.domain.audit.models import ActorContext
from vaultlog.domain.identity.exceptions import (
    MfaEnrollmentRequiredError,
    StepUpRequiredError,
    TokenValidationError,
)
from vaultlog.infrastructure.database.identity_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from vaultlog.infrastructure.email.logging_sender import LoggingEmailSender
from vaultlog.infrastructure.email.smtp import SmtpEmailSender
from vaultlog.infrastructure.security.mfa import PyotpTotpVerifier
from vaultlog.infrastructure.security.passwords import Argon2Hasher
from vaultlog.infrastructure.security.rate_limit import RedisRateLimiter
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
) -> Callable[[UUID], TenantUnitOfWork]:
    def factory(tenant_id: UUID) -> TenantUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, TenantContext(tenant_id=tenant_id))

    return factory


async def get_rate_limiter(request: Request) -> RedisRateLimiter:
    return cast(RedisRateLimiter, request.app.state.rate_limiter)


async def _enforce_rate_limit(
    limiter: RedisRateLimiter,
    key: str,
    *,
    capacity: int,
    window_seconds: int,
    fail_closed: bool,
) -> None:
    allowed = await limiter.check(
        key,
        capacity=capacity,
        window_seconds=window_seconds,
        fail_closed=fail_closed,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(window_seconds)},
        )


def rate_limit(
    bucket: str,
    *,
    capacity: int,
    window_seconds: int,
    fail_closed: bool = False,
    by: Literal["ip", "user"] = "ip",
) -> Callable[..., Awaitable[None]]:
    async def dependency_ip(
        request: Request,
        limiter: RedisRateLimiter = Depends(get_rate_limiter),
    ) -> None:
        identity = request.client.host if request.client else "unknown"
        await _enforce_rate_limit(
            limiter,
            f"rl:{bucket}:{identity}",
            capacity=capacity,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
        )

    async def dependency_user(
        principal: Principal = Depends(current_principal),
        limiter: RedisRateLimiter = Depends(get_rate_limiter),
    ) -> None:
        await _enforce_rate_limit(
            limiter,
            f"rl:{bucket}:{principal.user_id}",
            capacity=capacity,
            window_seconds=window_seconds,
            fail_closed=fail_closed,
        )

    return dependency_user if by == "user" else dependency_ip


def get_register_user(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    tenant_uow_factory: Callable[[UUID], TenantUnitOfWork] = Depends(
        get_tenant_uow_factory_for_tenant
    ),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> RegisterUser:
    provision = ProvisionTenantKey(tenant_uow_factory, kek, encryptor)
    return RegisterUser(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
        provision_tenant_key=provision,
    )


def get_login_user(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> LoginUser:
    return LoginUser(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_refresh_tokens(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> RefreshTokens:
    return RefreshTokens(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_logout_session(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> LogoutSession:
    return LogoutSession(
        uow_factory,
        passwords,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_start_totp_enrollment(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> StartTotpEnrollment:
    return StartTotpEnrollment(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_confirm_totp_enrollment(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> ConfirmTotpEnrollment:
    return ConfirmTotpEnrollment(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_complete_mfa_login(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> CompleteMfaLogin:
    return CompleteMfaLogin(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_step_up_verify(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> StepUpVerify:
    return StepUpVerify(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
    )


def get_disable_mfa(
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    seed_encryptor: AesGcmSeedEncryptor = Depends(get_seed_encryptor),
    totp_verifier: PyotpTotpVerifier = Depends(get_totp_verifier),
    tokens: TokenService = Depends(get_token_service),
    rate_limiter: RedisRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> DisableMfa:
    return DisableMfa(
        uow_factory,
        seed_encryptor,
        totp_verifier,
        tokens,
        settings.refresh_token_ttl_days,
        rate_limiter,
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


@lru_cache
def get_email_sender() -> SmtpEmailSender | LoggingEmailSender:
    settings = get_settings()
    if settings.environment == "test":
        return LoggingEmailSender()
    return SmtpEmailSender(settings)


async def require_mfa_if_owner(
    principal: Principal = Depends(current_principal),
    uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
) -> Principal:
    async with uow_factory() as uow:
        role = await uow.memberships.get_role(principal.user_id)
        user = await uow.users.get(principal.user_id)
        if user is None:
            raise _unauthorized
        if role == "owner" and not user.mfa_enabled:
            raise MfaEnrollmentRequiredError("MFA enrollment required")
    return principal


def get_tenant_uow(
    principal: Principal = Depends(current_principal),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> TenantUnitOfWork:
    context = TenantContext(tenant_id=principal.tenant_id)
    return SqlAlchemyUnitOfWork(session_factory, context)


def get_tenant_uow_factory(
    principal: Principal = Depends(current_principal),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_app_session_factory),
) -> Callable[[], TenantUnitOfWork]:
    context = TenantContext(tenant_id=principal.tenant_id)

    def factory() -> TenantUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, context)

    return factory


def get_get_current_user(
    identity_uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    tenant_uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
) -> GetCurrentUser:
    return GetCurrentUser(identity_uow_factory, tenant_uow_factory)


def get_record_access_denial(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
) -> RecordAccessDenial:
    return RecordAccessDenial(uow_factory)


def get_create_vault(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> CreateVault:
    return CreateVault(uow_factory, record_denial)


def get_list_vaults(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
) -> ListVaults:
    return ListVaults(uow_factory)


def get_get_vault(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
) -> GetVault:
    return GetVault(uow_factory)


def get_update_vault(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> UpdateVault:
    return UpdateVault(uow_factory, record_denial)


def get_delete_vault(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> DeleteVault:
    return DeleteVault(uow_factory, record_denial)


def get_manage_grant(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> ManageGrant:
    return ManageGrant(uow_factory, record_denial)


def get_list_grants(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> ListGrants:
    return ListGrants(uow_factory, record_denial)


def get_create_secret(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> CreateSecret:
    return CreateSecret(uow_factory, kek, encryptor, record_denial)


def get_list_secrets(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
) -> ListSecrets:
    return ListSecrets(uow_factory, kek, encryptor)


def get_reveal_secret(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> RevealSecret:
    return RevealSecret(uow_factory, kek, encryptor, record_denial)


def get_rotate_secret(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> RotateSecret:
    return RotateSecret(uow_factory, kek, encryptor, record_denial)


def get_delete_secret(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    kek: LocalKEKProvider = Depends(get_kek_provider),
    encryptor: AesGcmSecretEncryptor = Depends(get_secret_encryptor),
    record_denial: RecordAccessDenial = Depends(get_record_access_denial),
) -> DeleteSecret:
    return DeleteSecret(uow_factory, kek, encryptor, record_denial)


def get_list_audit_events(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
) -> ListAuditEvents:
    return ListAuditEvents(uow_factory)


def _org_use_case_deps(
    settings: Settings = Depends(get_settings),
    email_sender: SmtpEmailSender | LoggingEmailSender = Depends(get_email_sender),
) -> tuple[str, SmtpEmailSender | LoggingEmailSender]:
    return settings.invite_base_url, email_sender


def get_get_organization(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> GetOrganization:
    invite_base_url, email_sender = org_deps
    return GetOrganization(uow_factory, invite_base_url, email_sender)


def get_create_invitation(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    identity_uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> CreateInvitation:
    invite_base_url, email_sender = org_deps
    return CreateInvitation(uow_factory, identity_uow_factory, invite_base_url, email_sender)


def get_list_invitations(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> ListInvitations:
    invite_base_url, email_sender = org_deps
    return ListInvitations(uow_factory, invite_base_url, email_sender)


def get_revoke_invitation(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> RevokeInvitation:
    invite_base_url, email_sender = org_deps
    return RevokeInvitation(uow_factory, invite_base_url, email_sender)


def get_preview_invitation(
    identity_uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
) -> PreviewInvitation:
    return PreviewInvitation(identity_uow_factory)


def get_accept_invitation(
    tenant_uow_factory: Callable[[UUID], TenantUnitOfWork] = Depends(
        get_tenant_uow_factory_for_tenant
    ),
    identity_uow_factory: Callable[[], IdentityUnitOfWork] = Depends(get_identity_uow_factory),
    passwords: Argon2Hasher = Depends(get_password_hasher),
) -> AcceptInvitation:
    return AcceptInvitation(tenant_uow_factory, identity_uow_factory, passwords)


def get_list_members(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> ListMembers:
    invite_base_url, email_sender = org_deps
    return ListMembers(uow_factory, invite_base_url, email_sender)


def get_remove_member(
    uow_factory: Callable[[], TenantUnitOfWork] = Depends(get_tenant_uow_factory),
    org_deps: tuple[str, SmtpEmailSender | LoggingEmailSender] = Depends(_org_use_case_deps),
) -> RemoveMember:
    invite_base_url, email_sender = org_deps
    return RemoveMember(uow_factory, invite_base_url, email_sender)

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.access.services import org_capabilities_for_role
from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.domain.identity.models import (
    CurrentUserView,
    EnrollmentResult,
    LoginResult,
    TokenPair,
    UserCapabilities,
)
from vaultlog.domain.identity.ports import (
    PasswordHasher,
    RateLimitGate,
    SeedEncryptor,
    TokenIssuer,
    TotpVerifier,
)
from vaultlog.domain.identity.services import IdentityService, MfaService
from vaultlog.domain.secrets.exceptions import TenantKeyProvisionError

if TYPE_CHECKING:
    from vaultlog.application.secrets.use_cases import ProvisionTenantKey


def _build_identity_service(
    uow: IdentityUnitOfWork,
    passwords: PasswordHasher,
    tokens: TokenIssuer,
    refresh_ttl_days: int,
    rate_limiter: RateLimitGate,
) -> IdentityService:
    return IdentityService(
        users=uow.users,
        memberships=uow.memberships,
        sessions=uow.sessions,
        refresh_tokens=uow.refresh_tokens,
        organizations=uow.organizations,
        passwords=passwords,
        tokens=tokens,
        refresh_ttl_days=refresh_ttl_days,
        rate_limiter=rate_limiter,
    )


def _build_mfa_service(
    uow: IdentityUnitOfWork,
    seed_encryptor: SeedEncryptor,
    totp_verifier: TotpVerifier,
    tokens: TokenIssuer,
    refresh_ttl_days: int,
    rate_limiter: RateLimitGate,
) -> MfaService:
    return MfaService(
        users=uow.users,
        memberships=uow.memberships,
        sessions=uow.sessions,
        refresh_tokens=uow.refresh_tokens,
        totp_secrets=uow.totp_secrets,
        recovery_codes=uow.recovery_codes,
        seed_encryptor=seed_encryptor,
        totp_verifier=totp_verifier,
        tokens=tokens,
        refresh_ttl_days=refresh_ttl_days,
        rate_limiter=rate_limiter,
    )


class RegisterUser:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
        provision_tenant_key: ProvisionTenantKey | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter
        self._provision_tenant_key = provision_tenant_key

    async def execute(
        self,
        email: str,
        password: str,
        organization_name: str,
    ) -> uuid.UUID:
        async with self._uow_factory() as uow:
            service = _build_identity_service(
                uow,
                self._passwords,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            user_id, tenant_id = await service.register(email, password, organization_name)
            await uow.commit()

        if self._provision_tenant_key is not None:
            for attempt in range(2):
                try:
                    await self._provision_tenant_key.execute(tenant_id)
                    break
                except Exception:
                    if attempt == 1:
                        raise TenantKeyProvisionError(
                            "Tenant encryption key could not be provisioned"
                        ) from None

        return user_id


class LoginUser:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(
        self,
        email: str,
        password: str,
        user_agent: str | None,
    ) -> LoginResult:
        async with self._uow_factory() as uow:
            service = _build_identity_service(
                uow,
                self._passwords,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            result = await service.login(email, password, user_agent)
            await uow.commit()
            return result


class RefreshTokens:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(self, raw_refresh_token: str) -> TokenPair:
        auth_error: AuthenticationError | None = None
        async with self._uow_factory() as uow:
            service = _build_identity_service(
                uow,
                self._passwords,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            try:
                pair = await service.refresh(raw_refresh_token)
            except AuthenticationError as exc:
                await uow.commit()
                auth_error = exc
            else:
                await uow.commit()
                return pair
        assert auth_error is not None
        raise auth_error


class LogoutSession:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(self, raw_refresh_token: str) -> None:
        async with self._uow_factory() as uow:
            service = _build_identity_service(
                uow,
                self._passwords,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            await service.logout(raw_refresh_token)
            await uow.commit()


class StartTotpEnrollment:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(self, user_id: uuid.UUID, email: str) -> EnrollmentResult:
        async with self._uow_factory() as uow:
            service = _build_mfa_service(
                uow,
                self._seed_encryptor,
                self._totp_verifier,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            result = await service.start_enrollment(user_id, email)
            await uow.commit()
            return result


class ConfirmTotpEnrollment:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(self, user_id: uuid.UUID, code: str) -> list[str]:
        async with self._uow_factory() as uow:
            service = _build_mfa_service(
                uow,
                self._seed_encryptor,
                self._totp_verifier,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            codes = await service.confirm_enrollment(user_id, code)
            await uow.commit()
            return codes


class CompleteMfaLogin:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(
        self,
        challenge_token: str,
        code: str,
        user_agent: str | None,
    ) -> TokenPair:
        async with self._uow_factory() as uow:
            service = _build_mfa_service(
                uow,
                self._seed_encryptor,
                self._totp_verifier,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            pair = await service.complete_login(challenge_token, code, user_agent)
            await uow.commit()
            return pair


class StepUpVerify:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        code: str,
        purpose: str,
    ) -> str:
        async with self._uow_factory() as uow:
            service = _build_mfa_service(
                uow,
                self._seed_encryptor,
                self._totp_verifier,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            token = await service.step_up(user_id, session_id, code, purpose)
            await uow.commit()
            return token


class DisableMfa:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._uow_factory = uow_factory
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def execute(self, user_id: uuid.UUID) -> None:
        async with self._uow_factory() as uow:
            service = _build_mfa_service(
                uow,
                self._seed_encryptor,
                self._totp_verifier,
                self._tokens,
                self._refresh_ttl_days,
                self._rate_limiter,
            )
            await service.disable_mfa(user_id)
            await uow.commit()


@dataclass(frozen=True)
class SessionPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    session_id: uuid.UUID
    amr: tuple[str, ...]


class GetCurrentUser:
    def __init__(
        self,
        identity_uow_factory: Callable[[], IdentityUnitOfWork],
        tenant_uow_factory: Callable[[], TenantUnitOfWork],
    ) -> None:
        self._identity_uow_factory = identity_uow_factory
        self._tenant_uow_factory = tenant_uow_factory

    async def execute(self, principal: SessionPrincipal) -> CurrentUserView:
        async with self._identity_uow_factory() as identity_uow:
            user = await identity_uow.users.get(principal.user_id)
            if user is None or not user.is_active:
                raise AuthenticationError("Not authenticated")

        async with self._tenant_uow_factory() as tenant_uow:
            role = await tenant_uow.membership_access.get_role(
                principal.user_id,
                principal.tenant_id,
            )
            membership_id = await tenant_uow.membership_access.get_membership_id(
                principal.user_id,
                principal.tenant_id,
            )
            org_name = await tenant_uow.organizations.get_name(principal.tenant_id)
            if role is None or membership_id is None or org_name is None:
                raise AuthenticationError("Not authenticated")

        caps = org_capabilities_for_role(role)
        return CurrentUserView(
            user_id=principal.user_id,
            email=user.email,
            mfa_enabled=user.mfa_enabled,
            mfa_enrollment_required=role is OrgRole.OWNER and not user.mfa_enabled,
            membership_id=membership_id,
            role=role,
            organization_id=principal.tenant_id,
            organization_name=org_name,
            session_id=principal.session_id,
            amr=principal.amr,
            capabilities=UserCapabilities(**caps),
        )

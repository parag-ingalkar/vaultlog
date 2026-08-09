from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    MfaEnrollmentError,
    MfaVerificationError,
    RegistrationConflictError,
    TokenValidationError,
)
from vaultlog.domain.identity.models import EnrollmentResult, LoginResult, TokenPair
from vaultlog.domain.identity.password import validate_password_strength
from vaultlog.domain.identity.ports import (
    MembershipRepository,
    OrganizationRepository,
    PasswordHasher,
    RateLimitGate,
    RecoveryCodeRepository,
    RefreshTokenRepository,
    SeedEncryptor,
    SessionRepository,
    TokenIssuer,
    TotpSecretRepository,
    TotpVerifier,
    UserRepository,
)
from vaultlog.domain.identity.rate_limits import (
    LOGIN_ACCOUNT_CAPACITY,
    LOGIN_ACCOUNT_WINDOW_SECONDS,
    MFA_VERIFY_CAPACITY,
    MFA_VERIFY_WINDOW_SECONDS,
)

# Dummy Argon2id hash used to equalize timing when the user does not exist.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


async def _issue_credentials(
    *,
    user_id: uuid.UUID,
    memberships: MembershipRepository,
    sessions: SessionRepository,
    refresh_tokens: RefreshTokenRepository,
    tokens: TokenIssuer,
    refresh_ttl_days: int,
    user_agent: str | None,
    amr: tuple[str, ...],
) -> TokenPair:
    tenant_id = await memberships.get_tenant_id(user_id)
    if tenant_id is None:
        raise AuthenticationError("Invalid email or password")

    session = await sessions.add(user_id=user_id, user_agent=user_agent, amr=amr)
    raw_refresh = tokens.generate_refresh_token()
    await refresh_tokens.add(
        session_id=session.id,
        token_hash=tokens.hash_refresh_token(raw_refresh),
        expires_at=datetime.now(UTC) + timedelta(days=refresh_ttl_days),
    )

    access = tokens.mint_access_token(user_id, tenant_id, session.id, amr=amr)
    return TokenPair(access_token=access, refresh_token=raw_refresh)


class IdentityService:
    """Auth business rules: registration, login, refresh rotation, logout."""

    def __init__(
        self,
        *,
        users: UserRepository,
        memberships: MembershipRepository,
        sessions: SessionRepository,
        refresh_tokens: RefreshTokenRepository,
        organizations: OrganizationRepository,
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._sessions = sessions
        self._refresh_tokens = refresh_tokens
        self._organizations = organizations
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def register(
        self,
        email: str,
        password: str,
        organization_name: str,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        validate_password_strength(password)
        normalized = email.strip().lower()

        if await self._users.get_by_email(normalized) is not None:
            raise RegistrationConflictError("Registration failed")

        if await self._memberships.has_membership_for_email(normalized):
            raise RegistrationConflictError("Registration failed")

        user = await self._users.add(
            email=normalized,
            password_hash=self._passwords.hash(password),
        )
        org_id = await self._organizations.add(organization_name)
        await self._memberships.add(tenant_id=org_id, user_id=user.id, role="owner")
        return user.id, org_id

    async def login(
        self,
        email: str,
        password: str,
        user_agent: str | None,
    ) -> LoginResult:
        normalized = email.strip().lower()
        allowed = await self._rate_limiter.check(
            f"rl:login:acct:{normalized}",
            capacity=LOGIN_ACCOUNT_CAPACITY,
            window_seconds=LOGIN_ACCOUNT_WINDOW_SECONDS,
            fail_closed=True,
        )
        if not allowed:
            raise AuthenticationError("Invalid email or password")

        user = await self._users.get_by_email(normalized)
        if user is None or not user.is_active:
            self._passwords.verify(password, _DUMMY_PASSWORD_HASH)
            raise AuthenticationError("Invalid email or password")
        if not self._passwords.verify(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if user.mfa_enabled:
            challenge = self._tokens.mint_challenge_token(user.id)
            return LoginResult(kind="mfa_required", challenge_token=challenge)

        pair = await _issue_credentials(
            user_id=user.id,
            memberships=self._memberships,
            sessions=self._sessions,
            refresh_tokens=self._refresh_tokens,
            tokens=self._tokens,
            refresh_ttl_days=self._refresh_ttl_days,
            user_agent=user_agent,
            amr=("pwd",),
        )
        return LoginResult(kind="tokens", pair=pair)

    async def refresh(self, raw_refresh_token: str) -> TokenPair:
        token_hash = self._tokens.hash_refresh_token(raw_refresh_token)
        stored = await self._refresh_tokens.get_by_hash_for_update(token_hash)
        now = datetime.now(UTC)

        if stored is None:
            raise AuthenticationError("Invalid refresh token")

        session = await self._sessions.get(stored.session_id)
        if session is None or session.revoked_at is not None:
            raise AuthenticationError("Invalid refresh token")

        if stored.used_at is not None or stored.revoked_at is not None:
            await self._sessions.revoke(
                session.id,
                revoked_at=now,
                reason="refresh_reuse_detected",
            )
            raise AuthenticationError("Invalid refresh token")

        if stored.expires_at <= now:
            await self._sessions.revoke(
                session.id,
                revoked_at=now,
                reason="refresh_expired",
            )
            raise AuthenticationError("Invalid refresh token")

        raw_new = self._tokens.generate_refresh_token()
        new_token = await self._refresh_tokens.add(
            session_id=session.id,
            token_hash=self._tokens.hash_refresh_token(raw_new),
            expires_at=now + timedelta(days=self._refresh_ttl_days),
        )
        await self._refresh_tokens.mark_used(
            stored.id,
            used_at=now,
            replaced_by_id=new_token.id,
        )
        await self._sessions.touch(session.id, last_used_at=now)

        tenant_id = await self._memberships.get_tenant_id(session.user_id)
        if tenant_id is None:
            raise AuthenticationError("Invalid refresh token")

        access = self._tokens.mint_access_token(
            session.user_id,
            tenant_id,
            session.id,
            amr=session.amr,
        )
        return TokenPair(access_token=access, refresh_token=raw_new)

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = self._tokens.hash_refresh_token(raw_refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is None:
            return
        session = await self._sessions.get(stored.session_id)
        if session is not None and session.revoked_at is None:
            await self._sessions.revoke(
                session.id,
                revoked_at=datetime.now(UTC),
                reason="user_logout",
            )


class MfaService:
    """MFA enrollment, login completion, step-up, and disable."""

    def __init__(
        self,
        *,
        users: UserRepository,
        memberships: MembershipRepository,
        sessions: SessionRepository,
        refresh_tokens: RefreshTokenRepository,
        totp_secrets: TotpSecretRepository,
        recovery_codes: RecoveryCodeRepository,
        seed_encryptor: SeedEncryptor,
        totp_verifier: TotpVerifier,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
        rate_limiter: RateLimitGate,
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._sessions = sessions
        self._refresh_tokens = refresh_tokens
        self._totp_secrets = totp_secrets
        self._recovery_codes = recovery_codes
        self._seed_encryptor = seed_encryptor
        self._totp_verifier = totp_verifier
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days
        self._rate_limiter = rate_limiter

    async def start_enrollment(self, user_id: uuid.UUID, email: str) -> EnrollmentResult:
        await self._totp_secrets.delete_for_user(user_id)
        seed = self._totp_verifier.generate_seed()
        nonce, ciphertext = self._seed_encryptor.encrypt(user_id, seed)
        await self._totp_secrets.add(user_id, ciphertext, nonce, confirmed=False)
        uri = self._totp_verifier.provisioning_uri(seed, email)
        return EnrollmentResult(provisioning_uri=uri)

    async def confirm_enrollment(self, user_id: uuid.UUID, code: str) -> list[str]:
        record = await self._totp_secrets.get_unconfirmed(user_id)
        if record is None:
            raise MfaEnrollmentError("No pending enrollment")

        seed = self._seed_encryptor.decrypt(user_id, record.seed_nonce, record.encrypted_seed)
        if not self._totp_verifier.verify_totp(seed, code):
            raise MfaEnrollmentError("Invalid code")

        now = datetime.now(UTC)
        await self._totp_secrets.confirm(user_id, now)
        await self._users.set_mfa_enabled(user_id, True)

        await self._recovery_codes.delete_for_user(user_id)
        codes = self._totp_verifier.generate_recovery_codes()
        hashes = [self._totp_verifier.hash_recovery_code(raw) for raw in codes]
        await self._recovery_codes.add_batch(user_id, hashes)
        return codes

    async def _verify_totp_code(self, user_id: uuid.UUID, code: str) -> bool:
        record = await self._totp_secrets.get_confirmed(user_id)
        if record is None:
            return False
        seed = self._seed_encryptor.decrypt(user_id, record.seed_nonce, record.encrypted_seed)
        return self._totp_verifier.verify_totp(seed, code)

    async def _redeem_recovery_code(self, user_id: uuid.UUID, code: str) -> bool:
        code_hash = self._totp_verifier.hash_recovery_code(code)
        return await self._recovery_codes.redeem_for_update(user_id, code_hash)

    async def complete_login(
        self,
        challenge_token: str,
        code: str,
        user_agent: str | None,
    ) -> TokenPair:
        try:
            user_id = self._tokens.verify_challenge_token(challenge_token)
        except TokenValidationError as exc:
            raise MfaVerificationError("Invalid or expired challenge") from exc

        allowed = await self._rate_limiter.check(
            f"rl:mfa:{user_id}",
            capacity=MFA_VERIFY_CAPACITY,
            window_seconds=MFA_VERIFY_WINDOW_SECONDS,
            fail_closed=True,
        )
        if not allowed:
            raise MfaVerificationError("Invalid code")

        user = await self._users.get(user_id)
        if user is None or not user.is_active or not user.mfa_enabled:
            raise MfaVerificationError("Invalid or expired challenge")

        ok = await self._verify_totp_code(user_id, code) or await self._redeem_recovery_code(
            user_id, code
        )
        if not ok:
            raise MfaVerificationError("Invalid code")

        return await _issue_credentials(
            user_id=user_id,
            memberships=self._memberships,
            sessions=self._sessions,
            refresh_tokens=self._refresh_tokens,
            tokens=self._tokens,
            refresh_ttl_days=self._refresh_ttl_days,
            user_agent=user_agent,
            amr=("pwd", "totp"),
        )

    async def step_up(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        code: str,
        purpose: str,
    ) -> str:
        if not await self._verify_totp_code(user_id, code):
            raise MfaVerificationError("Invalid code")
        return self._tokens.mint_step_up_token(user_id, session_id, purpose)

    async def disable_mfa(self, user_id: uuid.UUID) -> None:
        await self._totp_secrets.delete_for_user(user_id)
        await self._recovery_codes.delete_for_user(user_id)
        await self._users.set_mfa_enabled(user_id, False)

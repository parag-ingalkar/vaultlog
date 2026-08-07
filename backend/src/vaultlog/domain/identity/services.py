from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    RegistrationConflictError,
)
from vaultlog.domain.identity.models import TokenPair
from vaultlog.domain.identity.password import validate_password_strength
from vaultlog.domain.identity.ports import (
    MembershipRepository,
    OrganizationRepository,
    PasswordHasher,
    RefreshTokenRepository,
    SessionRepository,
    TokenIssuer,
    UserRepository,
)

# Dummy Argon2id hash used to equalize timing when the user does not exist.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


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
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._sessions = sessions
        self._refresh_tokens = refresh_tokens
        self._organizations = organizations
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days

    async def register(
        self,
        email: str,
        password: str,
        organization_name: str,
    ) -> uuid.UUID:
        validate_password_strength(password)
        normalized = email.strip().lower()

        if await self._users.get_by_email(normalized) is not None:
            raise RegistrationConflictError("Registration failed")

        user = await self._users.add(
            email=normalized,
            password_hash=self._passwords.hash(password),
        )
        org_id = await self._organizations.add(organization_name)
        await self._memberships.add(tenant_id=org_id, user_id=user.id, role="owner")
        return user.id

    async def login(
        self,
        email: str,
        password: str,
        user_agent: str | None,
    ) -> TokenPair:
        user = await self._users.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            self._passwords.verify(password, _DUMMY_PASSWORD_HASH)
            raise AuthenticationError("Invalid email or password")
        if not self._passwords.verify(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        tenant_id = await self._memberships.get_default_tenant_id(user.id)
        if tenant_id is None:
            raise AuthenticationError("Invalid email or password")

        session = await self._sessions.add(user_id=user.id, user_agent=user_agent)
        raw_refresh = self._tokens.generate_refresh_token()
        await self._refresh_tokens.add(
            session_id=session.id,
            token_hash=self._tokens.hash_refresh_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=self._refresh_ttl_days),
        )

        access = self._tokens.mint_access_token(user.id, tenant_id, session.id)
        return TokenPair(access_token=access, refresh_token=raw_refresh)

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

        tenant_id = await self._memberships.get_default_tenant_id(session.user_id)
        if tenant_id is None:
            raise AuthenticationError("Invalid refresh token")

        access = self._tokens.mint_access_token(session.user_id, tenant_id, session.id)
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

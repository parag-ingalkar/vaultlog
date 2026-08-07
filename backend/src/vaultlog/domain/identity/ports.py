from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from vaultlog.domain.identity.models import (
    AccessTokenClaims,
    AuthSession,
    RefreshToken,
    User,
)


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, email: str, password_hash: str) -> User: ...


class MembershipRepository(Protocol):
    async def add(self, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None: ...

    async def get_default_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID | None: ...


class SessionRepository(Protocol):
    async def add(self, user_id: uuid.UUID, user_agent: str | None) -> AuthSession: ...

    async def get(self, session_id: uuid.UUID) -> AuthSession | None: ...

    async def revoke(
        self,
        session_id: uuid.UUID,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...

    async def touch(self, session_id: uuid.UUID, *, last_used_at: datetime) -> None: ...


class RefreshTokenRepository(Protocol):
    async def add(
        self,
        session_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken: ...

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def mark_used(
        self,
        token_id: uuid.UUID,
        *,
        used_at: datetime,
        replaced_by_id: uuid.UUID,
    ) -> None: ...


class OrganizationRepository(Protocol):
    async def add(self, name: str) -> uuid.UUID: ...


class PasswordHasher(Protocol):
    def hash(self, plaintext: str) -> str: ...

    def verify(self, plaintext: str, password_hash: str) -> bool: ...


class TokenIssuer(Protocol):
    def mint_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        amr: tuple[str, ...] = ("pwd",),
    ) -> str: ...

    def verify_access_token(self, token: str) -> AccessTokenClaims: ...

    def generate_refresh_token(self) -> str: ...

    def hash_refresh_token(self, raw_token: str) -> str: ...

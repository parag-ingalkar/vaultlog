from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    email: str
    password_hash: str
    is_active: bool
    mfa_enabled: bool


@dataclass(frozen=True)
class AuthSession:
    id: uuid.UUID
    user_id: uuid.UUID
    revoked_at: datetime | None
    revocation_reason: str | None
    user_agent: str | None
    last_used_at: datetime


@dataclass(frozen=True)
class RefreshToken:
    id: uuid.UUID
    session_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    replaced_by_id: uuid.UUID | None


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    session_id: uuid.UUID
    amr: tuple[str, ...]


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str

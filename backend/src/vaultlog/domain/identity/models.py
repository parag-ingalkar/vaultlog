from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from vaultlog.domain.access.models import OrgRole


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
    amr: tuple[str, ...] = ("pwd",)


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
class TotpSecret:
    id: uuid.UUID
    user_id: uuid.UUID
    encrypted_seed: bytes
    seed_nonce: bytes
    confirmed: bool
    confirmed_at: datetime | None


@dataclass(frozen=True)
class RecoveryCode:
    id: uuid.UUID
    user_id: uuid.UUID
    code_hash: str
    used_at: datetime | None


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


@dataclass(frozen=True)
class LoginResult:
    kind: Literal["tokens", "mfa_required"]
    pair: TokenPair | None = None
    challenge_token: str | None = None


@dataclass(frozen=True)
class EnrollmentResult:
    provisioning_uri: str


@dataclass(frozen=True)
class UserCapabilities:
    can_create_vaults: bool
    can_write_secrets: bool
    can_manage_members: bool
    can_manage_invitations: bool
    can_read_audit: bool


@dataclass(frozen=True)
class CurrentUserView:
    user_id: uuid.UUID
    email: str
    mfa_enabled: bool
    mfa_enrollment_required: bool
    membership_id: uuid.UUID
    role: OrgRole
    organization_id: uuid.UUID
    organization_name: str
    session_id: uuid.UUID
    amr: tuple[str, ...]
    capabilities: UserCapabilities

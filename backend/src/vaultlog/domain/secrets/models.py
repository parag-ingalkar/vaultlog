from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Secret:
    id: uuid.UUID
    tenant_id: uuid.UUID
    vault_id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class SecretVersion:
    id: uuid.UUID
    tenant_id: uuid.UUID
    secret_id: uuid.UUID
    version: int
    ciphertext: bytes
    nonce: bytes
    dek_version: int
    created_by_user_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True)
class TenantKeyVersion:
    tenant_id: uuid.UUID
    version: int
    wrapped_dek: bytes
    wrap_nonce: bytes
    wrapping_key_id: str
    status: str


@dataclass(frozen=True)
class SecretMetaView:
    id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_at: datetime
    updated_at: datetime

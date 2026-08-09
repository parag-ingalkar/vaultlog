from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from vaultlog.domain.access.models import OrgRole, VaultPermission


@dataclass(frozen=True)
class Vault:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(frozen=True)
class GrantView:
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    org_role: OrgRole
    permission: VaultPermission
    granted_at: datetime

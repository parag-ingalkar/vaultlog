from __future__ import annotations

import uuid
from typing import Protocol

from vaultlog.domain.access.models import OrgRole, VaultPermission


class MembershipAccessPort(Protocol):
    async def get_role(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> OrgRole | None: ...

    async def get_membership_id(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> uuid.UUID | None: ...

    async def get_membership_tenant(self, membership_id: uuid.UUID) -> uuid.UUID | None: ...


class VaultAccessPort(Protocol):
    async def exists_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> bool: ...


class VaultGrantAccessPort(Protocol):
    async def get_permission(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> VaultPermission | None: ...

    async def list_vault_ids_for_user(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID]: ...

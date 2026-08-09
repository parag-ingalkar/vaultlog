from __future__ import annotations

import uuid
from typing import Protocol

from vaultlog.domain.access.models import VaultPermission
from vaultlog.domain.vaults.models import Vault


class VaultRepository(Protocol):
    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by_user_id: uuid.UUID,
    ) -> Vault: ...

    async def get_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> Vault | None: ...

    async def list_active(
        self,
        tenant_id: uuid.UUID,
        *,
        vault_ids: list[uuid.UUID] | None = None,
    ) -> list[Vault]: ...

    async def soft_delete(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> None: ...

    async def update(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> Vault: ...


class VaultGrantRepository(Protocol):
    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        permission: VaultPermission,
        granted_by_user_id: uuid.UUID,
    ) -> bool: ...

    async def delete(
        self,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bool: ...

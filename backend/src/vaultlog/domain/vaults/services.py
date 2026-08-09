from __future__ import annotations

import builtins
import uuid
from dataclasses import dataclass
from datetime import datetime

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import Action, VaultPermission
from vaultlog.domain.access.ports import MembershipAccessPort
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.vaults.models import GrantView
from vaultlog.domain.vaults.ports import VaultGrantRepository, VaultRepository


@dataclass(frozen=True)
class VaultView:
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class VaultService:
    def __init__(
        self,
        vaults: VaultRepository,
        grants: VaultGrantRepository,
        memberships: MembershipAccessPort,
        policy: PolicyService,
    ) -> None:
        self._vaults = vaults
        self._grants = grants
        self._memberships = memberships
        self._policy = policy

    async def create(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> VaultView:
        await self._policy.require_org(user_id, tenant_id, Action.VAULT_CREATE)

        vault = await self._vaults.add(
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by_user_id=user_id,
        )

        membership_id = await self._memberships.get_membership_id(user_id, tenant_id)
        if membership_id is None:
            raise ForbiddenError("Access denied")

        await self._grants.upsert(
            tenant_id=tenant_id,
            vault_id=vault.id,
            membership_id=membership_id,
            permission=VaultPermission.ADMIN,
            granted_by_user_id=user_id,
        )
        return VaultView(
            id=vault.id,
            name=vault.name,
            description=vault.description,
            created_at=vault.created_at,
        )

    async def list(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[VaultView]:
        allowed_ids = await self._policy.list_accessible_vault_ids(user_id, tenant_id)
        rows = await self._vaults.list_active(tenant_id, vault_ids=allowed_ids)
        return [
            VaultView(
                id=vault.id,
                name=vault.name,
                description=vault.description,
                created_at=vault.created_at,
            )
            for vault in rows
        ]

    async def get(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> VaultView:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_READ_META)
        vault = await self._vaults.get_active(vault_id, tenant_id)
        if vault is None:
            raise NotFoundError("Vault not found")
        return VaultView(
            id=vault.id,
            name=vault.name,
            description=vault.description,
            created_at=vault.created_at,
        )

    async def update(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> VaultView:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.VAULT_UPDATE)
        vault = await self._vaults.update(
            vault_id,
            tenant_id,
            name=name,
            description=description,
            clear_description=clear_description,
        )
        return VaultView(
            id=vault.id,
            name=vault.name,
            description=vault.description,
            created_at=vault.created_at,
        )

    async def delete(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        if not step_up_proven:
            raise ForbiddenError("Step-up authentication required")
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.VAULT_DELETE)
        await self._vaults.soft_delete(vault_id, tenant_id)

    async def upsert_grant(
        self,
        actor_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
        permission: VaultPermission,
    ) -> bool:
        await self._policy.require_vault(actor_user_id, tenant_id, vault_id, Action.GRANT_MANAGE)

        target_tenant = await self._memberships.get_membership_tenant(target_membership_id)
        if target_tenant != tenant_id:
            raise NotFoundError("Membership not found")

        return await self._grants.upsert(
            tenant_id=tenant_id,
            vault_id=vault_id,
            membership_id=target_membership_id,
            permission=permission,
            granted_by_user_id=actor_user_id,
        )

    async def revoke_grant(
        self,
        actor_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
    ) -> None:
        await self._policy.require_vault(actor_user_id, tenant_id, vault_id, Action.GRANT_MANAGE)
        deleted = await self._grants.delete(vault_id, target_membership_id, tenant_id)
        if not deleted:
            raise NotFoundError("Grant not found")

    async def list_grants(
        self,
        actor_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> builtins.list[GrantView]:
        await self._policy.require_vault(actor_user_id, tenant_id, vault_id, Action.GRANT_MANAGE)
        return await self._grants.list_for_vault(vault_id, tenant_id)

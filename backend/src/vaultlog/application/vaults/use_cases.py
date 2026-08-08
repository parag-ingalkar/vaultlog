from __future__ import annotations

import uuid
from collections.abc import Callable

from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.models import VaultPermission
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.vaults.services import VaultService, VaultView


def build_policy_service(uow: TenantUnitOfWork) -> PolicyService:
    return PolicyService(
        memberships=uow.membership_access,
        vaults=uow.vault_access,
        grants=uow.grant_access,
    )


def build_vault_service(uow: TenantUnitOfWork) -> VaultService:
    policy = build_policy_service(uow)
    return VaultService(
        vaults=uow.vaults,
        grants=uow.vault_grants,
        memberships=uow.membership_access,
        policy=policy,
    )


class CreateVault:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> VaultView:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            view = await service.create(user_id, tenant_id, name, description)
            await uow.commit()
            return view


class ListVaults:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[VaultView]:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            return await service.list(user_id, tenant_id)


class UpdateVault:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> VaultView:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            view = await service.update(
                user_id,
                tenant_id,
                vault_id,
                name=name,
                description=description,
                clear_description=clear_description,
            )
            await uow.commit()
            return view


class DeleteVault:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            await service.delete(
                user_id,
                tenant_id,
                vault_id,
                step_up_proven=step_up_proven,
            )
            await uow.commit()


class ManageGrant:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def grant(
        self,
        actor_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
        permission: VaultPermission,
    ) -> None:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            await service.upsert_grant(
                actor_user_id,
                tenant_id,
                vault_id,
                target_membership_id,
                permission,
            )
            await uow.commit()

    async def revoke(
        self,
        actor_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
    ) -> None:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            await service.revoke_grant(
                actor_user_id,
                tenant_id,
                vault_id,
                target_membership_id,
            )
            await uow.commit()

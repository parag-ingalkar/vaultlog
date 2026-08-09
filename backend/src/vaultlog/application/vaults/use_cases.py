from __future__ import annotations

import uuid
from collections.abc import Callable

from vaultlog.application.audit.helpers import build_audit_service
from vaultlog.application.audit.use_cases import RecordAccessDenial, record_denial_if_needed
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.access.models import VaultPermission
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.audit.models import ActorContext
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
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        name: str,
        description: str | None,
    ) -> VaultView:
        try:
            async with self._uow_factory() as uow:
                service = build_vault_service(uow)
                view = await service.create(actor.user_id, actor.tenant_id, name, description)
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="vault.created",
                    target_type="vault",
                    target_id=view.id,
                    metadata={"name": name},
                )
                await uow.commit()
                return view
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class ListVaults:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[VaultView]:
        async with self._uow_factory() as uow:
            service = build_vault_service(uow)
            return await service.list(user_id, tenant_id)


class UpdateVault:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> VaultView:
        try:
            async with self._uow_factory() as uow:
                service = build_vault_service(uow)
                view = await service.update(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    name=name,
                    description=description,
                    clear_description=clear_description,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="vault.updated",
                    target_type="vault",
                    target_id=vault_id,
                )
                await uow.commit()
                return view
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class DeleteVault:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        try:
            async with self._uow_factory() as uow:
                service = build_vault_service(uow)
                await service.delete(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    step_up_proven=step_up_proven,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="vault.deleted",
                    target_type="vault",
                    target_id=vault_id,
                )
                await uow.commit()
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class ManageGrant:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._record_denial = record_denial

    async def grant(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
        permission: VaultPermission,
    ) -> None:
        try:
            async with self._uow_factory() as uow:
                service = build_vault_service(uow)
                created = await service.upsert_grant(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    target_membership_id,
                    permission,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="grant.created" if created else "grant.updated",
                    target_type="vault",
                    target_id=vault_id,
                    metadata={
                        "membership_id": str(target_membership_id),
                        "permission": permission.value,
                    },
                )
                await uow.commit()
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise

    async def revoke(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        target_membership_id: uuid.UUID,
    ) -> None:
        try:
            async with self._uow_factory() as uow:
                service = build_vault_service(uow)
                await service.revoke_grant(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    target_membership_id,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="grant.revoked",
                    target_type="vault",
                    target_id=vault_id,
                    metadata={"membership_id": str(target_membership_id)},
                )
                await uow.commit()
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise

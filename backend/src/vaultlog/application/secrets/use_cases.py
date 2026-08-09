from __future__ import annotations

import uuid
from collections.abc import Callable

from vaultlog.application.audit.helpers import build_audit_service
from vaultlog.application.audit.use_cases import RecordAccessDenial, record_denial_if_needed
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.audit.models import ActorContext
from vaultlog.domain.secrets.key_service import TenantKeyService
from vaultlog.domain.secrets.models import SecretMetaView
from vaultlog.domain.secrets.ports import KEKProvider, SecretEncryptor
from vaultlog.domain.secrets.services import SecretService


def build_policy_service(uow: TenantUnitOfWork) -> PolicyService:
    return PolicyService(
        memberships=uow.membership_access,
        vaults=uow.vault_access,
        grants=uow.grant_access,
    )


def build_tenant_key_service(
    uow: TenantUnitOfWork,
    kek: KEKProvider,
    encryptor: SecretEncryptor,
) -> TenantKeyService:
    return TenantKeyService(
        keys=uow.tenant_keys,
        kek=kek,
        encryptor=encryptor,
    )


def build_secret_service(
    uow: TenantUnitOfWork,
    kek: KEKProvider,
    encryptor: SecretEncryptor,
) -> SecretService:
    policy = build_policy_service(uow)
    keys = build_tenant_key_service(uow, kek, encryptor)
    return SecretService(
        secrets=uow.secrets,
        versions=uow.secret_versions,
        policy=policy,
        keys=keys,
        encryptor=encryptor,
    )


class ProvisionTenantKey:
    def __init__(
        self,
        uow_factory: Callable[[uuid.UUID], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor

    async def execute(self, tenant_id: uuid.UUID) -> int:
        async with self._uow_factory(tenant_id) as uow:
            service = build_tenant_key_service(uow, self._kek, self._encryptor)
            version = await service.provision(tenant_id)
            await uow.commit()
            return version


class CreateSecret:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        name: str,
        plaintext: str,
        description: str | None,
    ) -> SecretMetaView:
        try:
            async with self._uow_factory() as uow:
                service = build_secret_service(uow, self._kek, self._encryptor)
                view = await service.create(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    name,
                    plaintext,
                    description,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="secret.created",
                    target_type="secret",
                    target_id=view.id,
                    metadata={"vault_id": str(vault_id)},
                )
                await uow.commit()
                return view
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class ListSecrets:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> list[SecretMetaView]:
        async with self._uow_factory() as uow:
            service = build_secret_service(uow, self._kek, self._encryptor)
            return await service.list(user_id, tenant_id, vault_id)


class RevealSecret:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        version: int | None,
    ) -> tuple[SecretMetaView, str, int]:
        try:
            async with self._uow_factory() as uow:
                service = build_secret_service(uow, self._kek, self._encryptor)
                meta, plaintext, revealed_version = await service.reveal(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    secret_id,
                    version,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="secret.revealed",
                    target_type="secret",
                    target_id=secret_id,
                    metadata={"vault_id": str(vault_id), "version": revealed_version},
                )
                await uow.commit()
                return meta, plaintext, revealed_version
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class RotateSecret:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        new_plaintext: str,
    ) -> SecretMetaView:
        try:
            async with self._uow_factory() as uow:
                service = build_secret_service(uow, self._kek, self._encryptor)
                view, dek_version = await service.rotate(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    secret_id,
                    new_plaintext,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="secret.rotated",
                    target_type="secret",
                    target_id=secret_id,
                    metadata={
                        "vault_id": str(vault_id),
                        "new_version": view.current_version,
                        "dek_version": dek_version,
                    },
                )
                await uow.commit()
                return view
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise


class DeleteSecret:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        kek: KEKProvider,
        encryptor: SecretEncryptor,
        record_denial: RecordAccessDenial,
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor
        self._record_denial = record_denial

    async def execute(
        self,
        actor: ActorContext,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        try:
            async with self._uow_factory() as uow:
                service = build_secret_service(uow, self._kek, self._encryptor)
                await service.delete(
                    actor.user_id,
                    actor.tenant_id,
                    vault_id,
                    secret_id,
                    step_up_proven=step_up_proven,
                )
                audit = build_audit_service(uow)
                await audit.record(
                    actor=actor,
                    action="secret.deleted",
                    target_type="secret",
                    target_id=secret_id,
                    metadata={"vault_id": str(vault_id)},
                )
                await uow.commit()
        except ForbiddenError as exc:
            await record_denial_if_needed(self._record_denial, actor, exc)
            raise

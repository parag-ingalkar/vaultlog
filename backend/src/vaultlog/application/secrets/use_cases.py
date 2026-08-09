from __future__ import annotations

import uuid
from collections.abc import Callable

from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.services import PolicyService
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
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        name: str,
        plaintext: str,
        description: str | None,
    ) -> SecretMetaView:
        async with self._uow_factory() as uow:
            service = build_secret_service(uow, self._kek, self._encryptor)
            view = await service.create(
                user_id,
                tenant_id,
                vault_id,
                name,
                plaintext,
                description,
            )
            await uow.commit()
            return view


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
    ) -> None:
        self._uow_factory = uow_factory
        self._kek = kek
        self._encryptor = encryptor

    async def execute(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        version: int | None,
    ) -> tuple[SecretMetaView, str, int]:
        async with self._uow_factory() as uow:
            service = build_secret_service(uow, self._kek, self._encryptor)
            meta, plaintext, revealed_version = await service.reveal(
                user_id,
                tenant_id,
                vault_id,
                secret_id,
                version,
            )
            await uow.commit()
            return meta, plaintext, revealed_version


class RotateSecret:
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
        secret_id: uuid.UUID,
        new_plaintext: str,
    ) -> SecretMetaView:
        async with self._uow_factory() as uow:
            service = build_secret_service(uow, self._kek, self._encryptor)
            view = await service.rotate(
                user_id,
                tenant_id,
                vault_id,
                secret_id,
                new_plaintext,
            )
            await uow.commit()
            return view


class DeleteSecret:
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
        secret_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        async with self._uow_factory() as uow:
            service = build_secret_service(uow, self._kek, self._encryptor)
            await service.delete(
                user_id,
                tenant_id,
                vault_id,
                secret_id,
                step_up_proven=step_up_proven,
            )
            await uow.commit()

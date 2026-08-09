from __future__ import annotations

import uuid

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import Action
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.secrets.aad import secret_aad
from vaultlog.domain.secrets.key_service import TenantKeyService
from vaultlog.domain.secrets.models import Secret, SecretMetaView
from vaultlog.domain.secrets.ports import (
    SecretEncryptor,
    SecretRepository,
    SecretVersionRepository,
)


def _meta(secret: Secret) -> SecretMetaView:
    return SecretMetaView(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        current_version=secret.current_version,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
    )


class SecretService:
    def __init__(
        self,
        secrets: SecretRepository,
        versions: SecretVersionRepository,
        policy: PolicyService,
        keys: TenantKeyService,
        encryptor: SecretEncryptor,
    ) -> None:
        self._secrets = secrets
        self._versions = versions
        self._policy = policy
        self._keys = keys
        self._encryptor = encryptor

    async def create(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        name: str,
        plaintext: str,
        description: str | None,
    ) -> SecretMetaView:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_WRITE)

        secret = await self._secrets.add(
            tenant_id=tenant_id,
            vault_id=vault_id,
            name=name,
            description=description,
            created_by_user_id=user_id,
            current_version=1,
        )

        dek, dek_version = await self._keys.load_active_dek(tenant_id)
        aad = secret_aad(tenant_id, vault_id, secret.id, 1)
        nonce, ciphertext = self._encryptor.encrypt_secret(dek, plaintext.encode(), aad)

        await self._versions.add(
            tenant_id=tenant_id,
            secret_id=secret.id,
            version=1,
            ciphertext=ciphertext,
            nonce=nonce,
            dek_version=dek_version,
            created_by_user_id=user_id,
        )
        return _meta(secret)

    async def list(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> list[SecretMetaView]:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_READ_META)
        rows = await self._secrets.list_active(vault_id, tenant_id)
        return [_meta(secret) for secret in rows]

    async def reveal(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        version: int | None,
    ) -> tuple[SecretMetaView, str, int]:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_REVEAL)

        secret = await self._secrets.get_active(secret_id, vault_id, tenant_id)
        if secret is None:
            raise NotFoundError("Secret not found")

        wanted = version if version is not None else secret.current_version
        row = await self._versions.get(secret.id, wanted, tenant_id)
        if row is None:
            raise NotFoundError("Secret version not found")

        dek = await self._keys.load_dek_version(tenant_id, row.dek_version)
        aad = secret_aad(tenant_id, vault_id, secret.id, row.version)
        plaintext = self._encryptor.decrypt_secret(
            dek,
            row.nonce,
            row.ciphertext,
            aad,
        ).decode()
        return _meta(secret), plaintext, wanted

    async def rotate(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        new_plaintext: str,
    ) -> tuple[SecretMetaView, int]:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_WRITE)

        secret = await self._secrets.get_active_for_update(secret_id, vault_id, tenant_id)
        if secret is None:
            raise NotFoundError("Secret not found")

        new_version = secret.current_version + 1
        dek, dek_version = await self._keys.load_active_dek(tenant_id)
        aad = secret_aad(tenant_id, vault_id, secret.id, new_version)
        nonce, ciphertext = self._encryptor.encrypt_secret(
            dek,
            new_plaintext.encode(),
            aad,
        )

        await self._versions.add(
            tenant_id=tenant_id,
            secret_id=secret.id,
            version=new_version,
            ciphertext=ciphertext,
            nonce=nonce,
            dek_version=dek_version,
            created_by_user_id=user_id,
        )

        updated = await self._secrets.update_current_version(
            secret_id=secret.id,
            tenant_id=tenant_id,
            current_version=new_version,
        )
        return _meta(updated), dek_version

    async def delete(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        secret_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        if not step_up_proven:
            raise ForbiddenError("Step-up authentication required")
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_DELETE)

        secret = await self._secrets.get_active(secret_id, vault_id, tenant_id)
        if secret is None:
            raise NotFoundError("Secret not found")

        deleted = await self._secrets.soft_delete(secret_id, tenant_id)
        if not deleted:
            raise NotFoundError("Secret not found")

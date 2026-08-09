from __future__ import annotations

import uuid

from vaultlog.domain.secrets.aad import dek_wrap_aad
from vaultlog.domain.secrets.exceptions import CryptoError, NoActiveKeyError
from vaultlog.domain.secrets.ports import (
    KEKProvider,
    SecretEncryptor,
    TenantKeyRepository,
)


class TenantKeyService:
    def __init__(
        self,
        keys: TenantKeyRepository,
        kek: KEKProvider,
        encryptor: SecretEncryptor,
    ) -> None:
        self._keys = keys
        self._kek = kek
        self._encryptor = encryptor

    async def provision(self, tenant_id: uuid.UUID) -> int:
        existing = await self._keys.get_active(tenant_id)
        if existing is not None:
            return existing.version

        dek = self._encryptor.generate_dek()
        version = 1
        wrap_nonce, wrapped, key_id = self._kek.wrap(dek, dek_wrap_aad(tenant_id, version))
        await self._keys.add(
            tenant_id=tenant_id,
            version=version,
            wrapped_dek=wrapped,
            wrap_nonce=wrap_nonce,
            wrapping_key_id=key_id,
            status="active",
        )
        return version

    async def load_active_dek(self, tenant_id: uuid.UUID) -> tuple[bytes, int]:
        row = await self._keys.get_active(tenant_id)
        if row is None:
            raise NoActiveKeyError("Tenant has no active encryption key")
        dek = self._kek.unwrap(
            row.wrap_nonce,
            row.wrapped_dek,
            dek_wrap_aad(tenant_id, row.version),
            row.wrapping_key_id,
        )
        return dek, row.version

    async def load_dek_version(
        self,
        tenant_id: uuid.UUID,
        version: int,
    ) -> bytes:
        row = await self._keys.get_by_version(tenant_id, version)
        if row is None:
            raise CryptoError("Unknown key version")
        return self._kek.unwrap(
            row.wrap_nonce,
            row.wrapped_dek,
            dek_wrap_aad(tenant_id, version),
            row.wrapping_key_id,
        )

from __future__ import annotations

import uuid
from typing import Protocol

from vaultlog.domain.secrets.models import Secret, SecretVersion, TenantKeyVersion


class SecretEncryptor(Protocol):
    def generate_dek(self) -> bytes: ...

    def encrypt_secret(
        self,
        dek: bytes,
        plaintext: bytes,
        aad: bytes,
    ) -> tuple[bytes, bytes]: ...

    def decrypt_secret(
        self,
        dek: bytes,
        nonce: bytes,
        ciphertext: bytes,
        aad: bytes,
    ) -> bytes: ...


class KEKProvider(Protocol):
    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]: ...

    def unwrap(
        self,
        nonce: bytes,
        wrapped_dek: bytes,
        aad: bytes,
        wrapping_key_id: str,
    ) -> bytes: ...


class TenantKeyRepository(Protocol):
    async def get_active(self, tenant_id: uuid.UUID) -> TenantKeyVersion | None: ...

    async def get_by_version(
        self,
        tenant_id: uuid.UUID,
        version: int,
    ) -> TenantKeyVersion | None: ...

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        version: int,
        wrapped_dek: bytes,
        wrap_nonce: bytes,
        wrapping_key_id: str,
        status: str,
    ) -> TenantKeyVersion: ...


class SecretRepository(Protocol):
    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by_user_id: uuid.UUID,
        current_version: int,
    ) -> Secret: ...

    async def get_active(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None: ...

    async def get_active_for_update(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None: ...

    async def list_active(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[Secret]: ...

    async def soft_delete(
        self,
        secret_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bool: ...

    async def update_current_version(
        self,
        secret_id: uuid.UUID,
        tenant_id: uuid.UUID,
        current_version: int,
    ) -> Secret: ...


class SecretVersionRepository(Protocol):
    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        secret_id: uuid.UUID,
        version: int,
        ciphertext: bytes,
        nonce: bytes,
        dek_version: int,
        created_by_user_id: uuid.UUID,
    ) -> SecretVersion: ...

    async def get(
        self,
        secret_id: uuid.UUID,
        version: int,
        tenant_id: uuid.UUID,
    ) -> SecretVersion | None: ...

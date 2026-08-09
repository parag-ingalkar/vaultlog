from __future__ import annotations

from uuid import UUID


def secret_aad(tenant_id: UUID, vault_id: UUID, secret_id: UUID, version: int) -> bytes:
    return f"vaultlog:secret:v1:{tenant_id}:{vault_id}:{secret_id}:{version}".encode()


def dek_wrap_aad(tenant_id: UUID, key_version: int) -> bytes:
    return f"vaultlog:dek-wrap:v1:{tenant_id}:{key_version}".encode()

from __future__ import annotations

import uuid

import pytest

from vaultlog.domain.secrets.key_service import TenantKeyService


class FakeTenantKeyRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def get_active(self, tenant_id: uuid.UUID):
        for row in self.rows:
            if row["tenant_id"] == tenant_id and row["status"] == "active":
                from vaultlog.domain.secrets.models import TenantKeyVersion

                return TenantKeyVersion(
                    tenant_id=row["tenant_id"],
                    version=row["version"],
                    wrapped_dek=row["wrapped_dek"],
                    wrap_nonce=row["wrap_nonce"],
                    wrapping_key_id=row["wrapping_key_id"],
                    status=row["status"],
                )
        return None

    async def get_by_version(self, tenant_id: uuid.UUID, version: int):
        for row in self.rows:
            if row["tenant_id"] == tenant_id and row["version"] == version:
                from vaultlog.domain.secrets.models import TenantKeyVersion

                return TenantKeyVersion(
                    tenant_id=row["tenant_id"],
                    version=row["version"],
                    wrapped_dek=row["wrapped_dek"],
                    wrap_nonce=row["wrap_nonce"],
                    wrapping_key_id=row["wrapping_key_id"],
                    status=row["status"],
                )
        return None

    async def add(self, **kwargs):
        from vaultlog.domain.secrets.models import TenantKeyVersion

        self.rows.append(kwargs)
        return TenantKeyVersion(
            tenant_id=kwargs["tenant_id"],
            version=kwargs["version"],
            wrapped_dek=kwargs["wrapped_dek"],
            wrap_nonce=kwargs["wrap_nonce"],
            wrapping_key_id=kwargs["wrapping_key_id"],
            status=kwargs["status"],
        )


class FakeKEK:
    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]:
        return b"nonce", b"wrapped", "test-kek"

    def unwrap(
        self,
        nonce: bytes,
        wrapped_dek: bytes,
        aad: bytes,
        wrapping_key_id: str,
    ) -> bytes:
        assert nonce == b"nonce"
        assert wrapped_dek == b"wrapped"
        assert wrapping_key_id == "test-kek"
        return b"01234567890123456789012345678901"


class FakeEncryptor:
    def generate_dek(self) -> bytes:
        return b"01234567890123456789012345678901"

    def encrypt_secret(self, dek: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
        return b"n", b"ct"

    def decrypt_secret(
        self,
        dek: bytes,
        nonce: bytes,
        ciphertext: bytes,
        aad: bytes,
    ) -> bytes:
        return b"plain"


TENANT_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_provision_is_idempotent() -> None:
    repo = FakeTenantKeyRepository()
    service = TenantKeyService(repo, FakeKEK(), FakeEncryptor())
    v1 = await service.provision(TENANT_ID)
    v2 = await service.provision(TENANT_ID)
    assert v1 == 1
    assert v2 == 1
    assert len(repo.rows) == 1


@pytest.mark.asyncio
async def test_load_active_dek_round_trip() -> None:
    repo = FakeTenantKeyRepository()
    kek = FakeKEK()
    encryptor = FakeEncryptor()
    service = TenantKeyService(repo, kek, encryptor)
    await service.provision(TENANT_ID)
    dek, version = await service.load_active_dek(TENANT_ID)
    assert version == 1
    assert dek == encryptor.generate_dek()


@pytest.mark.asyncio
async def test_load_dek_version() -> None:
    repo = FakeTenantKeyRepository()
    service = TenantKeyService(repo, FakeKEK(), FakeEncryptor())
    await service.provision(TENANT_ID)
    dek = await service.load_dek_version(TENANT_ID, 1)
    assert dek == b"01234567890123456789012345678901"

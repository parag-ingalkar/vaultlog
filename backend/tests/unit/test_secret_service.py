from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.access.models import OrgRole, VaultPermission
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.secrets.models import Secret, SecretVersion
from vaultlog.domain.secrets.services import SecretService

USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
VAULT_ID = uuid.uuid4()
SECRET_ID = uuid.uuid4()


def _secret(current_version: int = 1) -> Secret:
    now = datetime.now(UTC)
    return Secret(
        id=SECRET_ID,
        tenant_id=TENANT_ID,
        vault_id=VAULT_ID,
        name="api-key",
        description=None,
        current_version=current_version,
        created_by_user_id=USER_ID,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


class FakeMembershipAccess:
    def __init__(self, role: OrgRole = OrgRole.ADMIN) -> None:
        self._role = role

    async def get_role(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> OrgRole | None:
        return self._role

    async def get_membership_id(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID | None:
        return uuid.uuid4()

    async def get_membership_tenant(self, membership_id: uuid.UUID) -> uuid.UUID | None:
        return TENANT_ID


class FakeVaultAccess:
    async def exists_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        return vault_id == VAULT_ID and tenant_id == TENANT_ID


class FakeGrantAccess:
    def __init__(self, permission: VaultPermission | None = VaultPermission.WRITE) -> None:
        self.permission = permission

    async def get_permission(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> VaultPermission | None:
        return self.permission

    async def list_vault_ids_for_user(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        return [VAULT_ID] if self.permission else []


class FakeSecretRepository:
    def __init__(self) -> None:
        self.secret = _secret()
        self.deleted = False

    async def add(self, **kwargs) -> Secret:
        self.secret = Secret(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            vault_id=kwargs["vault_id"],
            name=kwargs["name"],
            description=kwargs["description"],
            current_version=kwargs["current_version"],
            created_by_user_id=kwargs["created_by_user_id"],
            created_at=self.secret.created_at,
            updated_at=self.secret.updated_at,
            deleted_at=None,
        )
        return self.secret

    async def get_active(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None:
        if self.deleted or secret_id != self.secret.id:
            return None
        return self.secret

    async def get_active_for_update(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None:
        return await self.get_active(secret_id, vault_id, tenant_id)

    async def list_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> list[Secret]:
        return [self.secret] if not self.deleted else []

    async def soft_delete(self, secret_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        if secret_id != self.secret.id:
            return False
        self.deleted = True
        return True

    async def update_current_version(
        self,
        secret_id: uuid.UUID,
        tenant_id: uuid.UUID,
        current_version: int,
    ) -> Secret:
        self.secret = Secret(
            id=self.secret.id,
            tenant_id=self.secret.tenant_id,
            vault_id=self.secret.vault_id,
            name=self.secret.name,
            description=self.secret.description,
            current_version=current_version,
            created_by_user_id=self.secret.created_by_user_id,
            created_at=self.secret.created_at,
            updated_at=datetime.now(UTC),
            deleted_at=None,
        )
        return self.secret


class FakeVersionRepository:
    def __init__(self) -> None:
        self.versions: dict[int, SecretVersion] = {}

    async def add(self, **kwargs) -> SecretVersion:
        version = SecretVersion(
            id=uuid.uuid4(),
            tenant_id=kwargs["tenant_id"],
            secret_id=kwargs["secret_id"],
            version=kwargs["version"],
            ciphertext=kwargs["ciphertext"],
            nonce=kwargs["nonce"],
            dek_version=kwargs["dek_version"],
            created_by_user_id=kwargs["created_by_user_id"],
            created_at=datetime.now(UTC),
        )
        self.versions[kwargs["version"]] = version
        return version

    async def get(
        self,
        secret_id: uuid.UUID,
        version: int,
        tenant_id: uuid.UUID,
    ) -> SecretVersion | None:
        return self.versions.get(version)


class FakeKeyService:
    async def load_active_dek(self, tenant_id: uuid.UUID) -> tuple[bytes, int]:
        return b"01234567890123456789012345678901", 1

    async def load_dek_version(self, tenant_id: uuid.UUID, version: int) -> bytes:
        return b"01234567890123456789012345678901"


class FakeEncryptor:
    def encrypt_secret(self, dek: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
        self.last_plaintext = plaintext
        return b"nonce", b"ciphertext"

    def decrypt_secret(
        self,
        dek: bytes,
        nonce: bytes,
        ciphertext: bytes,
        aad: bytes,
    ) -> bytes:
        return getattr(self, "last_plaintext", b"revealed-value")


def build_service(
    role: OrgRole = OrgRole.ADMIN,
    grant: VaultPermission | None = VaultPermission.WRITE,
) -> SecretService:
    policy = PolicyService(
        memberships=FakeMembershipAccess(role),
        vaults=FakeVaultAccess(),
        grants=FakeGrantAccess(grant),
    )
    return SecretService(
        secrets=FakeSecretRepository(),
        versions=FakeVersionRepository(),
        policy=policy,
        keys=FakeKeyService(),
        encryptor=FakeEncryptor(),
    )


@pytest.mark.asyncio
async def test_create_secret_encrypts_value() -> None:
    service = build_service()
    meta = await service.create(
        USER_ID,
        TENANT_ID,
        VAULT_ID,
        "db-password",
        "hunter2",
        None,
    )
    assert meta.name == "db-password"
    assert meta.current_version == 1


@pytest.mark.asyncio
async def test_reveal_returns_plaintext() -> None:
    service = build_service()
    created = await service.create(USER_ID, TENANT_ID, VAULT_ID, "k", "hunter2", None)
    meta, plaintext, version = await service.reveal(
        USER_ID,
        TENANT_ID,
        VAULT_ID,
        created.id,
        None,
    )
    assert plaintext == "hunter2"
    assert version == 1
    assert meta.id == created.id


@pytest.mark.asyncio
async def test_rotate_increments_version() -> None:
    service = build_service()
    created = await service.create(USER_ID, TENANT_ID, VAULT_ID, "k", "v1", None)
    rotated, _dek_version = await service.rotate(USER_ID, TENANT_ID, VAULT_ID, created.id, "v2")
    assert rotated.current_version == 2


@pytest.mark.asyncio
async def test_delete_requires_step_up() -> None:
    service = build_service()
    created = await service.create(USER_ID, TENANT_ID, VAULT_ID, "k", "v1", None)
    with pytest.raises(ForbiddenError):
        await service.delete(
            USER_ID,
            TENANT_ID,
            VAULT_ID,
            created.id,
            step_up_proven=False,
        )


@pytest.mark.asyncio
async def test_viewer_cannot_write_secrets() -> None:
    service = build_service(role=OrgRole.VIEWER, grant=None)
    with pytest.raises(ForbiddenError):
        await service.create(USER_ID, TENANT_ID, VAULT_ID, "n", "v", None)

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import OrgRole, VaultPermission
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.vaults.models import Vault
from vaultlog.domain.vaults.services import VaultService

USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
VAULT_ID = uuid.uuid4()
MEMBERSHIP_ID = uuid.uuid4()


class FakeMembershipAccess:
    def __init__(self, role: OrgRole = OrgRole.MEMBER) -> None:
        self._role = role

    async def get_role(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> OrgRole | None:
        return self._role

    async def get_membership_id(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID | None:
        return MEMBERSHIP_ID

    async def get_membership_tenant(self, membership_id: uuid.UUID) -> uuid.UUID | None:
        return TENANT_ID if membership_id == MEMBERSHIP_ID else None


class FakeVaultAccess:
    async def exists_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        return vault_id == VAULT_ID and tenant_id == TENANT_ID


class FakeGrantAccess:
    def __init__(self) -> None:
        self.permission: VaultPermission | None = None

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
        return [VAULT_ID] if self.permission is not None else []


class FakeVaultRepository:
    def __init__(self) -> None:
        self.vaults: list[Vault] = []
        self.deleted: list[uuid.UUID] = []

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by_user_id: uuid.UUID,
    ) -> Vault:
        now = datetime.now(UTC)
        vault = Vault(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self.vaults.append(vault)
        return vault

    async def get_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> Vault | None:
        for vault in self.vaults:
            if vault.id == vault_id and vault.tenant_id == tenant_id and vault.deleted_at is None:
                return vault
        return None

    async def list_active(
        self,
        tenant_id: uuid.UUID,
        *,
        vault_ids: list[uuid.UUID] | None = None,
    ) -> list[Vault]:
        rows = [v for v in self.vaults if v.tenant_id == tenant_id and v.deleted_at is None]
        if vault_ids is not None:
            rows = [v for v in rows if v.id in vault_ids]
        return rows

    async def soft_delete(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        self.deleted.append(vault_id)

    async def update(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> Vault:
        raise NotImplementedError("not used in these tests")


class FakeGrantRepository:
    def __init__(self) -> None:
        self.grants: list[tuple[uuid.UUID, uuid.UUID, VaultPermission]] = []

    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        permission: VaultPermission,
        granted_by_user_id: uuid.UUID,
    ) -> bool:
        self.grants = [
            row for row in self.grants if not (row[0] == vault_id and row[1] == membership_id)
        ]
        self.grants.append((vault_id, membership_id, permission))
        return True

    async def delete(
        self,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bool:
        before = len(self.grants)
        self.grants = [
            row for row in self.grants if not (row[0] == vault_id and row[1] == membership_id)
        ]
        return len(self.grants) < before


def _service(role: OrgRole = OrgRole.MEMBER) -> tuple[VaultService, FakeGrantRepository]:
    memberships = FakeMembershipAccess(role)
    grants_access = FakeGrantAccess()
    grants = FakeGrantRepository()
    policy = PolicyService(memberships, FakeVaultAccess(), grants_access)
    service = VaultService(
        vaults=FakeVaultRepository(),
        grants=grants,
        memberships=memberships,
        policy=policy,
    )
    return service, grants


async def test_create_assigns_creator_admin_grant():
    service, grants = _service()
    view = await service.create(USER_ID, TENANT_ID, "Prod", "desc")
    assert view.name == "Prod"
    assert len(grants.grants) == 1
    assert grants.grants[0][2] is VaultPermission.ADMIN


async def test_delete_requires_step_up():
    service, _ = _service(OrgRole.OWNER)
    created = await service.create(USER_ID, TENANT_ID, "Prod", None)
    with pytest.raises(ForbiddenError, match="Step-up"):
        await service.delete(USER_ID, TENANT_ID, created.id, step_up_proven=False)


async def test_grant_revoke_honest_not_found():
    service, _ = _service(OrgRole.OWNER)
    created = await service.create(USER_ID, TENANT_ID, "Prod", None)
    with pytest.raises(NotFoundError):
        await service.revoke_grant(
            USER_ID,
            TENANT_ID,
            created.id,
            uuid.uuid4(),
        )


async def test_grant_rejects_foreign_membership():
    service, _ = _service(OrgRole.OWNER)
    created = await service.create(USER_ID, TENANT_ID, "Prod", None)
    with pytest.raises(NotFoundError):
        await service.upsert_grant(
            USER_ID,
            TENANT_ID,
            created.id,
            uuid.uuid4(),
            VaultPermission.READ,
        )

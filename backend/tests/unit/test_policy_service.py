from __future__ import annotations

import uuid

import pytest

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import Action, OrgRole, VaultPermission
from vaultlog.domain.access.services import PolicyService

USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
VAULT_ID = uuid.uuid4()


class FakeMembershipAccess:
    def __init__(self, role: OrgRole | None) -> None:
        self._role = role

    async def get_role(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> OrgRole | None:
        return self._role

    async def get_membership_id(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID | None:
        return uuid.uuid4() if self._role is not None else None

    async def get_membership_tenant(self, membership_id: uuid.UUID) -> uuid.UUID | None:
        return TENANT_ID


class FakeVaultAccess:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    async def exists_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        return self._exists


class FakeGrantAccess:
    def __init__(
        self,
        permission: VaultPermission | None = None,
        vault_ids: list[uuid.UUID] | None = None,
    ) -> None:
        self._permission = permission
        self._vault_ids = vault_ids or []

    async def get_permission(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> VaultPermission | None:
        return self._permission

    async def list_vault_ids_for_user(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        return self._vault_ids


def _policy(
    role: OrgRole | None,
    grant: VaultPermission | None,
    *,
    vault_exists: bool = True,
) -> PolicyService:
    return PolicyService(
        memberships=FakeMembershipAccess(role),
        vaults=FakeVaultAccess(vault_exists),
        grants=FakeGrantAccess(grant),
    )


ORG_ACTIONS = {
    Action.VAULT_LIST,
    Action.VAULT_CREATE,
    Action.MEMBER_INVITE,
    Action.MEMBER_REMOVE,
    Action.AUDIT_READ,
}

VAULT_ACTIONS = {
    Action.VAULT_UPDATE,
    Action.VAULT_DELETE,
    Action.GRANT_MANAGE,
    Action.SECRET_READ_META,
    Action.SECRET_REVEAL,
    Action.SECRET_WRITE,
    Action.SECRET_DELETE,
}


async def _evaluate(role: OrgRole, grant: VaultPermission | None, action: Action) -> bool:
    policy = _policy(role, grant)
    try:
        if action in ORG_ACTIONS:
            await policy.require_org(USER_ID, TENANT_ID, action)
        else:
            await policy.require_vault(USER_ID, TENANT_ID, VAULT_ID, action)
        return True
    except (ForbiddenError, NotFoundError):
        return False


MATRIX: list[tuple[OrgRole, VaultPermission | None, Action, bool]] = [
    (OrgRole.OWNER, None, Action.VAULT_CREATE, True),
    (OrgRole.OWNER, None, Action.VAULT_DELETE, True),
    (OrgRole.OWNER, None, Action.GRANT_MANAGE, True),
    (OrgRole.OWNER, None, Action.SECRET_DELETE, True),
    (OrgRole.ADMIN, None, Action.VAULT_CREATE, True),
    (OrgRole.ADMIN, None, Action.SECRET_WRITE, True),
    (OrgRole.ADMIN, None, Action.SECRET_DELETE, True),
    (OrgRole.OWNER, None, Action.AUDIT_READ, True),
    (OrgRole.ADMIN, None, Action.AUDIT_READ, True),
    (OrgRole.MEMBER, None, Action.AUDIT_READ, False),
    (OrgRole.MEMBER, None, Action.SECRET_READ_META, False),
    (OrgRole.MEMBER, VaultPermission.READ, Action.SECRET_READ_META, True),
    (OrgRole.MEMBER, VaultPermission.READ, Action.SECRET_WRITE, False),
    (OrgRole.MEMBER, VaultPermission.WRITE, Action.SECRET_WRITE, True),
    (OrgRole.MEMBER, VaultPermission.WRITE, Action.SECRET_DELETE, False),
    (OrgRole.MEMBER, VaultPermission.ADMIN, Action.SECRET_DELETE, True),
    (OrgRole.MEMBER, None, Action.GRANT_MANAGE, False),
    (OrgRole.MEMBER, None, Action.VAULT_DELETE, False),
    (OrgRole.VIEWER, VaultPermission.READ, Action.SECRET_READ_META, True),
    (OrgRole.VIEWER, VaultPermission.WRITE, Action.SECRET_WRITE, False),
    (OrgRole.VIEWER, None, Action.VAULT_CREATE, False),
    (OrgRole.VIEWER, VaultPermission.READ, Action.VAULT_LIST, True),
    (OrgRole.MEMBER, None, Action.VAULT_CREATE, True),
    (OrgRole.VIEWER, None, Action.MEMBER_INVITE, False),
    (OrgRole.ADMIN, None, Action.MEMBER_INVITE, True),
]


@pytest.mark.parametrize("role,grant,action,expected", MATRIX)
async def test_policy_matrix(role, grant, action, expected):
    assert await _evaluate(role, grant, action) is expected


async def test_missing_vault_returns_not_found():
    policy = _policy(OrgRole.MEMBER, VaultPermission.READ, vault_exists=False)
    with pytest.raises(NotFoundError):
        await policy.require_vault(USER_ID, TENANT_ID, VAULT_ID, Action.SECRET_READ_META)


async def test_owner_lists_all_vaults_unrestricted():
    policy = _policy(OrgRole.OWNER, None)
    assert await policy.list_accessible_vault_ids(USER_ID, TENANT_ID) is None


async def test_member_lists_grant_scoped_vaults():
    policy = PolicyService(
        memberships=FakeMembershipAccess(OrgRole.MEMBER),
        vaults=FakeVaultAccess(),
        grants=FakeGrantAccess(vault_ids=[VAULT_ID]),
    )
    assert await policy.list_accessible_vault_ids(USER_ID, TENANT_ID) == [VAULT_ID]

from __future__ import annotations

import uuid

import pytest

from tests.integration.fixtures.vaults import (
    ADMIN_USER,
    MEMBER_USER,
    ORG_ID,
    OWNER_USER,
    VAULT_ID,
    VIEWER_USER,
    seed_rbac_tenant,
)
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import Action, OrgRole, VaultPermission
from vaultlog.domain.access.services import PolicyService
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
async def rbac_tenant(owner_engine, app_engine):
    await seed_rbac_tenant(owner_engine, app_engine)


def _uow(app_engine, tenant_id: uuid.UUID) -> SqlAlchemyUnitOfWork:
    factory = build_session_factory(app_engine)
    return SqlAlchemyUnitOfWork(factory, TenantContext(tenant_id=tenant_id))


async def _grant(
    app_engine,
    membership_id: uuid.UUID,
    permission: VaultPermission,
    *,
    actor: uuid.UUID = ADMIN_USER,
) -> None:
    async with _uow(app_engine, ORG_ID) as uow:
        await uow.vault_grants.upsert(
            tenant_id=ORG_ID,
            vault_id=VAULT_ID,
            membership_id=membership_id,
            permission=permission,
            granted_by_user_id=actor,
        )
        await uow.commit()


async def _evaluate(
    app_engine,
    user_id: uuid.UUID,
    action: Action,
    *,
    grant: VaultPermission | None = None,
    membership_id: uuid.UUID | None = None,
) -> bool:
    if grant is not None and membership_id is not None:
        await _grant(app_engine, membership_id, grant)

    async with _uow(app_engine, ORG_ID) as uow:
        policy = PolicyService(
            memberships=uow.membership_access,
            vaults=uow.vault_access,
            grants=uow.grant_access,
        )
        try:
            if action in {
                Action.VAULT_LIST,
                Action.VAULT_CREATE,
                Action.MEMBER_INVITE,
                Action.MEMBER_REMOVE,
                Action.AUDIT_READ,
            }:
                await policy.require_org(user_id, ORG_ID, action)
            else:
                await policy.require_vault(user_id, ORG_ID, VAULT_ID, action)
            return True
        except (ForbiddenError, NotFoundError):
            return False


MATRIX = [
    (OrgRole.OWNER, None, Action.VAULT_CREATE, True, OWNER_USER, None),
    (OrgRole.OWNER, None, Action.VAULT_DELETE, True, OWNER_USER, None),
    (OrgRole.OWNER, None, Action.GRANT_MANAGE, True, OWNER_USER, None),
    (OrgRole.OWNER, None, Action.SECRET_DELETE, True, OWNER_USER, None),
    (OrgRole.ADMIN, None, Action.VAULT_CREATE, True, ADMIN_USER, None),
    (OrgRole.ADMIN, None, Action.SECRET_WRITE, True, ADMIN_USER, None),
    (OrgRole.ADMIN, None, Action.SECRET_DELETE, True, ADMIN_USER, None),
    (OrgRole.OWNER, None, Action.AUDIT_READ, True, OWNER_USER, None),
    (OrgRole.ADMIN, None, Action.AUDIT_READ, True, ADMIN_USER, None),
    (OrgRole.MEMBER, None, Action.AUDIT_READ, False, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.VAULT_CREATE, False, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.SECRET_READ_META, True, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.SECRET_WRITE, True, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.SECRET_DELETE, True, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.GRANT_MANAGE, False, MEMBER_USER, None),
    (OrgRole.MEMBER, None, Action.VAULT_DELETE, False, MEMBER_USER, None),
    (OrgRole.VIEWER, None, Action.SECRET_READ_META, True, VIEWER_USER, None),
    (OrgRole.VIEWER, None, Action.SECRET_REVEAL, True, VIEWER_USER, None),
    (OrgRole.VIEWER, None, Action.SECRET_WRITE, False, VIEWER_USER, None),
    (OrgRole.VIEWER, None, Action.VAULT_CREATE, False, VIEWER_USER, None),
]


@pytest.mark.parametrize("role,grant,action,expected,user_id,membership_id", MATRIX)
async def test_policy_matrix_integration(
    app_engine,
    rbac_tenant,
    role,
    grant,
    action,
    expected,
    user_id,
    membership_id,
):
    del role
    assert (
        await _evaluate(
            app_engine,
            user_id,
            action,
            grant=grant,
            membership_id=membership_id,
        )
        is expected
    )

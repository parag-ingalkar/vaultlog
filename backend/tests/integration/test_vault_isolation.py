from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.integration.fixtures.constants import TENANT_B, VAULT_A_ID
from tests.integration.fixtures.vaults import (
    ADMIN_USER,
    MEMBER_MEMBERSHIP,
    MEMBER_USER,
    ORG_ID,
    VAULT_ID,
    seed_rbac_tenant,
)
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.application.vaults.use_cases import (
    CreateVault,
    DeleteVault,
    ListVaults,
    ManageGrant,
    build_policy_service,
)
from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import Action, VaultPermission
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
async def rbac_tenant(owner_engine, app_engine):
    await seed_rbac_tenant(owner_engine, app_engine)


def _factory(app_engine, tenant_id: uuid.UUID):
    session_factory = build_session_factory(app_engine)

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, TenantContext(tenant_id=tenant_id))

    return factory


async def test_cross_tenant_vault_lookup_is_not_found(app_engine, rbac_tenant):
    async with _factory(app_engine, TENANT_B)() as uow:
        exists = await uow.vault_access.exists_active(VAULT_ID, TENANT_B)
        assert exists is False


async def test_forged_membership_grant_is_not_found(app_engine, rbac_tenant):
    manage = ManageGrant(_factory(app_engine, ORG_ID))
    with pytest.raises(NotFoundError):
        await manage.grant(
            ADMIN_USER,
            ORG_ID,
            VAULT_ID,
            uuid.uuid4(),
            VaultPermission.READ,
        )


async def test_soft_deleted_vault_is_hidden(app_engine, rbac_tenant, owner_engine):
    delete = DeleteVault(_factory(app_engine, ORG_ID))
    await delete.execute(ADMIN_USER, ORG_ID, VAULT_ID, step_up_proven=True)

    list_vaults = ListVaults(_factory(app_engine, ORG_ID))
    views = await list_vaults.execute(ADMIN_USER, ORG_ID)
    assert all(view.id != VAULT_ID for view in views)

    async with _factory(app_engine, ORG_ID)() as uow:
        assert await uow.vault_access.exists_active(VAULT_ID, ORG_ID) is False


async def test_grant_upsert_is_idempotent(app_engine, rbac_tenant, owner_engine):
    manage = ManageGrant(_factory(app_engine, ORG_ID))
    await manage.grant(
        ADMIN_USER,
        ORG_ID,
        VAULT_ID,
        MEMBER_MEMBERSHIP,
        VaultPermission.READ,
    )
    await manage.grant(
        ADMIN_USER,
        ORG_ID,
        VAULT_ID,
        MEMBER_MEMBERSHIP,
        VaultPermission.WRITE,
    )

    async with owner_engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT permission FROM vault_grant
                WHERE vault_id = :vault_id AND membership_id = :membership_id
                """
            ),
            {"vault_id": VAULT_ID, "membership_id": MEMBER_MEMBERSHIP},
        )
        rows = result.all()
        assert len(rows) == 1
        assert rows[0][0] == "write"


async def test_member_without_grant_cannot_write_after_revoke(app_engine, rbac_tenant):
    manage = ManageGrant(_factory(app_engine, ORG_ID))
    await manage.grant(
        ADMIN_USER,
        ORG_ID,
        VAULT_ID,
        MEMBER_MEMBERSHIP,
        VaultPermission.WRITE,
    )
    await manage.revoke(ADMIN_USER, ORG_ID, VAULT_ID, MEMBER_MEMBERSHIP)

    async with _factory(app_engine, ORG_ID)() as uow:
        policy = build_policy_service(uow)
        with pytest.raises(ForbiddenError):
            await policy.require_vault(
                MEMBER_USER,
                ORG_ID,
                VAULT_ID,
                Action.SECRET_WRITE,
            )


async def test_member_can_create_vault_and_list_it(app_engine, owner_engine):
    await seed_rbac_tenant(owner_engine, app_engine)
    create = CreateVault(_factory(app_engine, ORG_ID))
    view = await create.execute(MEMBER_USER, ORG_ID, "Member Vault", "mine")
    list_vaults = ListVaults(_factory(app_engine, ORG_ID))
    names = [v.name for v in await list_vaults.execute(MEMBER_USER, ORG_ID)]
    assert "Member Vault" in names
    assert view.id is not None


async def test_baseline_vault_still_isolated_between_tenants(scoped_session):
    session = await scoped_session(TENANT_B)
    try:
        result = await session.execute(
            text("SELECT id FROM vault WHERE id = :id"),
            {"id": str(VAULT_A_ID)},
        )
        assert result.all() == []
    finally:
        await session.rollback()
        await session.close()

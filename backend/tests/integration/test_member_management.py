from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.integration.fixtures.audit import make_actor, tenant_uow_factory
from tests.integration.fixtures.vaults import (
    ADMIN_MEMBERSHIP,
    ADMIN_USER,
    MEMBER_MEMBERSHIP,
    MEMBER_USER,
    ORG_ID,
    OWNER_MEMBERSHIP,
    OWNER_USER,
    PASSWORD_HASH,
    VIEWER_MEMBERSHIP,
    VIEWER_USER,
    seed_rbac_tenant,
)
from vaultlog.application.organizations.use_cases import RemoveMember
from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.organizations.exceptions import MemberConflictError
from vaultlog.infrastructure.email.logging_sender import LoggingEmailSender
from vaultlog.shared.config import get_settings

SECOND_ADMIN_USER = uuid.UUID("55555555-5555-5555-5555-555555555555")
SECOND_ADMIN_MEMBERSHIP = uuid.UUID("aaaaaaaa-5555-5555-5555-555555555555")


@pytest.fixture()
async def rbac_tenant(owner_engine, app_engine):
    await seed_rbac_tenant(owner_engine, app_engine)


async def _seed_second_admin(owner_engine) -> None:
    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO app_user (id, email, password_hash)
                VALUES (:id, 'admin2@rbac.test', :hash)
                """
            ),
            {"id": SECOND_ADMIN_USER, "hash": PASSWORD_HASH},
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(ORG_ID)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO membership (id, tenant_id, user_id, role)
                VALUES (:mid, :t, :uid, 'admin')
                """
            ),
            {"mid": SECOND_ADMIN_MEMBERSHIP, "t": ORG_ID, "uid": SECOND_ADMIN_USER},
        )


def _remove_member(app_engine) -> RemoveMember:
    settings = get_settings()
    return RemoveMember(
        tenant_uow_factory(app_engine, ORG_ID),
        invite_base_url=settings.invite_base_url,
        email_sender=LoggingEmailSender(),
    )


@pytest.mark.asyncio
async def test_admin_cannot_remove_owner(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    with pytest.raises(MemberConflictError, match="Cannot remove owner"):
        await remove.execute(
            make_actor(ADMIN_USER, ORG_ID),
            OWNER_MEMBERSHIP,
            step_up_proven=True,
        )


@pytest.mark.asyncio
async def test_admin_cannot_remove_admin(owner_engine, app_engine, rbac_tenant) -> None:
    await _seed_second_admin(owner_engine)
    remove = _remove_member(app_engine)
    with pytest.raises(MemberConflictError, match="Cannot remove this member"):
        await remove.execute(
            make_actor(ADMIN_USER, ORG_ID),
            SECOND_ADMIN_MEMBERSHIP,
            step_up_proven=True,
        )


@pytest.mark.asyncio
async def test_admin_can_remove_member(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    await remove.execute(
        make_actor(ADMIN_USER, ORG_ID),
        MEMBER_MEMBERSHIP,
        step_up_proven=True,
    )


@pytest.mark.asyncio
async def test_admin_can_remove_viewer(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    await remove.execute(
        make_actor(ADMIN_USER, ORG_ID),
        VIEWER_MEMBERSHIP,
        step_up_proven=True,
    )


@pytest.mark.asyncio
async def test_owner_can_remove_admin(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    await remove.execute(
        make_actor(OWNER_USER, ORG_ID),
        ADMIN_MEMBERSHIP,
        step_up_proven=True,
    )


@pytest.mark.asyncio
async def test_owner_cannot_remove_owner(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    with pytest.raises(MemberConflictError, match="Cannot remove owner"):
        await remove.execute(
            make_actor(OWNER_USER, ORG_ID),
            OWNER_MEMBERSHIP,
            step_up_proven=True,
        )


@pytest.mark.asyncio
async def test_cannot_remove_self(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    with pytest.raises(MemberConflictError, match="Cannot remove yourself"):
        await remove.execute(
            make_actor(ADMIN_USER, ORG_ID),
            ADMIN_MEMBERSHIP,
            step_up_proven=True,
        )


@pytest.mark.asyncio
async def test_viewer_cannot_remove_member(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    with pytest.raises(ForbiddenError):
        await remove.execute(
            make_actor(VIEWER_USER, ORG_ID),
            MEMBER_MEMBERSHIP,
            step_up_proven=True,
        )


@pytest.mark.asyncio
async def test_member_cannot_remove_member(app_engine, rbac_tenant) -> None:
    remove = _remove_member(app_engine)
    with pytest.raises(ForbiddenError):
        await remove.execute(
            make_actor(MEMBER_USER, ORG_ID),
            VIEWER_MEMBERSHIP,
            step_up_proven=True,
        )

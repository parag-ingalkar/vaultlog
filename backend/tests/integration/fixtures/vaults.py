"""RBAC integration fixtures: org with four roles and a shared vault."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.fixtures.constants import TENANT_A
from tests.integration.fixtures.tenant_keys import provision_tenant_encryption_key
from vaultlog.infrastructure.security.passwords import Argon2Hasher

ORG_ID = TENANT_A
VAULT_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

OWNER_USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
ADMIN_USER = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEMBER_USER = uuid.UUID("33333333-3333-3333-3333-333333333333")
VIEWER_USER = uuid.UUID("44444444-4444-4444-4444-444444444444")

OWNER_MEMBERSHIP = uuid.UUID("aaaaaaaa-1111-1111-1111-111111111111")
ADMIN_MEMBERSHIP = uuid.UUID("aaaaaaaa-2222-2222-2222-222222222222")
MEMBER_MEMBERSHIP = uuid.UUID("aaaaaaaa-3333-3333-3333-333333333333")
VIEWER_MEMBERSHIP = uuid.UUID("aaaaaaaa-4444-4444-4444-444444444444")

PASSWORD_HASH = Argon2Hasher().hash("correct horse battery")


async def seed_rbac_tenant(owner_engine: AsyncEngine, app_engine: AsyncEngine) -> None:
    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO app_user (id, email, password_hash)
                VALUES
                    (:owner, 'owner@rbac.test', :hash),
                    (:admin, 'admin@rbac.test', :hash),
                    (:member, 'member@rbac.test', :hash),
                    (:viewer, 'viewer@rbac.test', :hash)
                """
            ),
            {
                "owner": OWNER_USER,
                "admin": ADMIN_USER,
                "member": MEMBER_USER,
                "viewer": VIEWER_USER,
                "hash": PASSWORD_HASH,
            },
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(ORG_ID)},
        )
        await conn.execute(
            text("INSERT INTO organization (id, name) VALUES (:t, 'RBAC Org')"),
            {"t": ORG_ID},
        )
        await conn.execute(
            text(
                """
                INSERT INTO membership (id, tenant_id, user_id, role)
                VALUES
                    (:om, :t, :owner, 'owner'),
                    (:am, :t, :admin, 'admin'),
                    (:mm, :t, :member, 'member'),
                    (:vm, :t, :viewer, 'viewer')
                """
            ),
            {
                "om": OWNER_MEMBERSHIP,
                "am": ADMIN_MEMBERSHIP,
                "mm": MEMBER_MEMBERSHIP,
                "vm": VIEWER_MEMBERSHIP,
                "t": ORG_ID,
                "owner": OWNER_USER,
                "admin": ADMIN_USER,
                "member": MEMBER_USER,
                "viewer": VIEWER_USER,
            },
        )
        await conn.execute(
            text(
                """
                INSERT INTO vault (id, tenant_id, name, created_by_user_id)
                VALUES (:id, :t, 'RBAC Vault', :owner)
                """
            ),
            {"id": VAULT_ID, "t": ORG_ID, "owner": OWNER_USER},
        )

    await provision_tenant_encryption_key(app_engine, ORG_ID)

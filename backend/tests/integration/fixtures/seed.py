"""Seed baseline tenant data for isolation tests."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.fixtures.constants import SEED_USER_ID, TENANT_A, TENANT_B, VAULT_A_ID


async def seed_baseline_data(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :a, true)"),
            {"a": str(TENANT_A)},
        )
        await conn.execute(
            text("INSERT INTO organization (id, name) VALUES (:a, 'Tenant A')"),
            {"a": TENANT_A},
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :b, true)"),
            {"b": str(TENANT_B)},
        )
        await conn.execute(
            text("INSERT INTO organization (id, name) VALUES (:b, 'Tenant B')"),
            {"b": TENANT_B},
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(TENANT_A)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO vault (
                    id, tenant_id, name, description, created_by_user_id
                ) VALUES (
                    :id, :t, 'A secret vault', 'Baseline vault for isolation tests', :user_id
                )
                """
            ),
            {"id": VAULT_A_ID, "t": TENANT_A, "user_id": SEED_USER_ID},
        )

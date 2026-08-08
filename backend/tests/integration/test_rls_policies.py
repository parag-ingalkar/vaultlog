from __future__ import annotations

from scripts.rls.apply import TENANT_TABLES
from sqlalchemy import text


async def test_rls_enabled_and_forced_on_tenant_tables(owner_engine):
    async with owner_engine.connect() as conn:
        for table in sorted(TENANT_TABLES):
            result = await conn.execute(
                text(
                    """
                    SELECT c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = :table
                    """
                ),
                {"table": table},
            )
            row = result.one()
            assert row.relrowsecurity, f"{table} should have RLS enabled"
            assert row.relforcerowsecurity, f"{table} should have FORCE RLS"


async def test_tenant_isolation_policies_exist(owner_engine):
    async with owner_engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND policyname = 'tenant_isolation'
                """
            )
        )
        tables_with_policy = {row.tablename for row in result.all()}
        assert tables_with_policy == TENANT_TABLES

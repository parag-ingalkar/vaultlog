from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from scripts.rls.apply import TENANT_TABLES
from sqlalchemy import text

from vaultlog.shared.config import get_settings

pytestmark = pytest.mark.schema

BACKEND_ROOT = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "a1b2c3d4e5f6"


def _alembic_config() -> Config:
    settings = get_settings()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.migration_database_url)
    return cfg


async def _table_exists(engine, table: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass(:qualified_name) IS NOT NULL"),
            {"qualified_name": f"public.{table}"},
        )
        return bool(result.scalar())


async def _tenant_isolation_policies(engine) -> set[str]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_policies
                WHERE schemaname = 'public' AND policyname = 'tenant_isolation'
                """
            )
        )
        return {row.tablename for row in result.all()}


async def _rls_forced_on_all_tenant_tables(engine) -> bool:
    async with engine.connect() as conn:
        for table in TENANT_TABLES:
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
            if not row.relrowsecurity or not row.relforcerowsecurity:
                return False
    return True


async def _assert_at_head(engine) -> None:
    assert await _table_exists(engine, "membership")
    assert await _tenant_isolation_policies(engine) == TENANT_TABLES
    assert await _rls_forced_on_all_tenant_tables(engine)


@pytest.fixture(scope="session", autouse=True)
def restore_schema_head(migrated_schema):
    yield
    command.upgrade(_alembic_config(), "head")


def test_alembic_downgrade_upgrade_restores_rls(owner_engine) -> None:
    cfg = _alembic_config()

    asyncio.run(_assert_at_head(owner_engine))

    command.downgrade(cfg, INITIAL_REVISION)
    assert not asyncio.run(_table_exists(owner_engine, "membership"))
    assert asyncio.run(_table_exists(owner_engine, "organization"))
    assert asyncio.run(_table_exists(owner_engine, "vault"))

    command.upgrade(cfg, "head")
    asyncio.run(_assert_at_head(owner_engine))

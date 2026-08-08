"""Run Alembic migrations against the test database."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.fixtures.constants import TEST_DATABASE_NAME
from tests.integration.fixtures.database import _session_needs_integration_db
from vaultlog.shared.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]


async def _reset_public_schema(settings) -> None:
    url = settings.build_database_url(
        settings.migration_database_user,
        settings.migration_database_password,
        database_name=TEST_DATABASE_NAME,
    )
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO vaultlog_owner"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO vaultlog_app"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def migrated_schema(request, ensure_test_database) -> None:
    if not _session_needs_integration_db(request.session):
        return

    settings = get_settings()
    asyncio.run(_reset_public_schema(settings))

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.migration_database_url)
    command.upgrade(cfg, "head")

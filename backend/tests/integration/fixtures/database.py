"""Database engines and test database provisioning."""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.fixtures.constants import ADMIN_DATABASE_NAME, TEST_DATABASE_NAME
from vaultlog.shared.config import get_settings


def _session_needs_integration_db(session) -> bool:
    return any("integration" in item.nodeid for item in session.items)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


async def _database_exists(url: str) -> bool:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _create_test_database(settings) -> None:
    admin_url = settings.build_database_url(
        settings.migration_database_user,
        settings.migration_database_password,
        database_name=ADMIN_DATABASE_NAME,
    )
    admin_engine = create_async_engine(
        admin_url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME} OWNER vaultlog_owner"))
            await conn.execute(
                text(f"GRANT CONNECT ON DATABASE {TEST_DATABASE_NAME} TO vaultlog_app")
            )
    finally:
        admin_engine.sync_engine.dispose()


async def _create_test_database_bootstrap(settings) -> None:
    bootstrap_user = os.environ.get("TEST_DATABASE_BOOTSTRAP_USER", "postgres_bootstrap")
    bootstrap_password = os.environ.get(
        "TEST_DATABASE_BOOTSTRAP_PASSWORD",
        "postgres_bootstrap_password",
    )
    bootstrap_url = settings.build_database_url(
        bootstrap_user,
        bootstrap_password,
        database_name="postgres",
    )
    bootstrap_engine = create_async_engine(
        bootstrap_url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with bootstrap_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_NAME},
            )
            if exists.scalar() is None:
                await conn.execute(
                    text(f"CREATE DATABASE {TEST_DATABASE_NAME} OWNER vaultlog_owner")
                )
            await conn.execute(
                text(f"GRANT CONNECT ON DATABASE {TEST_DATABASE_NAME} TO vaultlog_app")
            )
            await conn.execute(text("ALTER ROLE vaultlog_owner CREATEDB"))
    finally:
        bootstrap_engine.sync_engine.dispose()


@pytest.fixture(scope="session")
def ensure_test_database(request) -> None:
    if not _session_needs_integration_db(request.session):
        return

    settings = get_settings()
    test_url = settings.build_database_url(
        settings.migration_database_user,
        settings.migration_database_password,
        database_name=TEST_DATABASE_NAME,
    )

    if asyncio.run(_database_exists(test_url)):
        return

    try:
        asyncio.run(_create_test_database(settings))
    except Exception:
        try:
            asyncio.run(_create_test_database_bootstrap(settings))
        except Exception as exc:
            msg = (
                f"Could not create {TEST_DATABASE_NAME}. "
                "Create it manually, grant CREATEDB to vaultlog_owner, or set "
                "TEST_DATABASE_BOOTSTRAP_USER/PASSWORD for compose bootstrap access."
            )
            raise RuntimeError(msg) from exc

    if not asyncio.run(_database_exists(test_url)):
        raise RuntimeError(f"{TEST_DATABASE_NAME} is still unreachable after bootstrap.")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def owner_engine(request, ensure_test_database, migrated_schema) -> AsyncEngine:
    if not _session_needs_integration_db(request.session):
        pytest.skip("owner_engine only for integration tests")

    settings = get_settings()
    engine = create_async_engine(
        settings.migration_database_url,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_engine(request, ensure_test_database, migrated_schema) -> AsyncEngine:
    if not _session_needs_integration_db(request.session):
        pytest.skip("app_engine only for integration tests")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()

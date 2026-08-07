from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from vaultlog.shared.config import get_settings

pytestmark = pytest.mark.asyncio(loop_scope="module")

settings = get_settings()

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
VAULT_A_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def owner_engine():
    """Migration/seed role: used only to seed fixture data."""
    engine = create_async_engine(settings.migration_database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def app_engine():
    """The RLS-enforced application role."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module", autouse=True)
async def seed_tenants(owner_engine):
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :a, true)"),
            {"a": str(TENANT_A)},
        )
        await conn.execute(
            text(
                "INSERT INTO organization (id, name) VALUES (:a, 'Tenant A') ON CONFLICT DO NOTHING"
            ),
            {"a": TENANT_A},
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :b, true)"),
            {"b": str(TENANT_B)},
        )
        await conn.execute(
            text(
                "INSERT INTO organization (id, name) VALUES (:b, 'Tenant B') ON CONFLICT DO NOTHING"
            ),
            {"b": TENANT_B},
        )
        await conn.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(TENANT_A)},
        )
        await conn.execute(
            text(
                "INSERT INTO vault (id, tenant_id, name) VALUES "
                "(:id, :t, 'A secret vault') ON CONFLICT DO NOTHING"
            ),
            {"id": VAULT_A_ID, "t": TENANT_A},
        )
    yield


@pytest.fixture()
def scoped_session(app_engine):
    """Yields a function that opens a session scoped to a given tenant."""

    factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async def _open(tenant_id):
        session = factory()
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        return session

    return _open

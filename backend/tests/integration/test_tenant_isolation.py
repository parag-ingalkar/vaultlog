from __future__ import annotations

from sqlalchemy import text

from tests.integration.conftest import TENANT_A, TENANT_B


async def test_tenant_a_sees_own_vaults(scoped_session):
    session = await scoped_session(TENANT_A)
    try:
        result = await session.execute(text("SELECT name FROM vault"))
        names = [row[0] for row in result.all()]
        assert names == ["A secret vault"]
    finally:
        await session.rollback()
        await session.close()


async def test_tenant_b_sees_no_vaults(scoped_session):
    session = await scoped_session(TENANT_B)
    try:
        result = await session.execute(text("SELECT id FROM vault"))
        assert result.all() == []
    finally:
        await session.rollback()
        await session.close()


async def test_cross_tenant_insert_is_rejected(scoped_session):
    session = await scoped_session(TENANT_B)
    try:
        await session.execute(
            text(
                "INSERT INTO vault (id, tenant_id, name) VALUES (gen_random_uuid(), :t, 'stolen')"
            ),
            {"t": str(TENANT_A)},
        )
        raise AssertionError("RLS WITH CHECK should have rejected the insert")
    except Exception:
        await session.rollback()
    finally:
        await session.close()


async def test_unscoped_connection_sees_nothing(app_engine):
    """No SET LOCAL at all: the fail-closed policy must yield zero rows, not an error."""
    async with app_engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM vault"))
        assert result.scalar() == 0


async def test_tenant_cannot_read_other_tenant_organization(scoped_session):
    session = await scoped_session(TENANT_B)
    try:
        result = await session.execute(text("SELECT name FROM organization"))
        names = [row[0] for row in result.all()]
        assert names == ["Tenant B"]
    finally:
        await session.rollback()
        await session.close()

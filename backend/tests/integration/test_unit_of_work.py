from __future__ import annotations

from sqlalchemy import text

from tests.integration.fixtures.constants import TENANT_A
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


async def test_uow_sets_tenant_context_and_rolls_back_on_error(app_engine):
    factory = build_session_factory(app_engine)
    uow = SqlAlchemyUnitOfWork(factory, TenantContext(tenant_id=TENANT_A))

    try:
        async with uow:
            result = await uow.session.execute(text("SELECT count(*) FROM vault"))
            assert result.scalar() == 1
            raise RuntimeError("simulate use-case failure")
    except RuntimeError:
        pass

    async with app_engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM vault"))
        assert result.scalar() == 0

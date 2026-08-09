from __future__ import annotations

import asyncio
import sys
import uuid

from vaultlog.application.audit.use_cases import VerifyTenantChain
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.infrastructure.database.engine import build_engine, build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from vaultlog.shared.config import get_settings


async def main(tenant_id: uuid.UUID) -> int:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, TenantContext(tenant_id=tenant_id))

    verifier = VerifyTenantChain(uow_factory)
    result = await verifier.execute(tenant_id)
    await engine.dispose()
    print(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: verify_chain.py <tenant-id>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(uuid.UUID(sys.argv[1]))))

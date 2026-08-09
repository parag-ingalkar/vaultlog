from __future__ import annotations

import uuid

from vaultlog.application.audit.use_cases import RecordAccessDenial
from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.domain.audit.models import ActorContext
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork

TEST_SESSION_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def make_actor(user_id: uuid.UUID, tenant_id: uuid.UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        session_id=TEST_SESSION_ID,
        tenant_id=tenant_id,
    )


def tenant_uow_factory(app_engine, tenant_id: uuid.UUID):
    session_factory = build_session_factory(app_engine)

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, TenantContext(tenant_id=tenant_id))

    return factory


def record_access_denial(app_engine, tenant_id: uuid.UUID) -> RecordAccessDenial:
    return RecordAccessDenial(tenant_uow_factory(app_engine, tenant_id))

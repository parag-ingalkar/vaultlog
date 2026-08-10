from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from tests.integration.fixtures.audit import make_actor, record_access_denial, tenant_uow_factory
from tests.integration.fixtures.vaults import (
    ADMIN_USER,
    MEMBER_USER,
    ORG_ID,
    OWNER_USER,
    VAULT_ID,
    VIEWER_USER,
    seed_rbac_tenant,
)
from vaultlog.application.audit.use_cases import ListAuditEvents, VerifyTenantChain
from vaultlog.application.secrets.use_cases import CreateSecret, RevealSecret, RotateSecret
from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.audit.exceptions import AuditMetadataError
from vaultlog.domain.audit.services import AuditService
from vaultlog.infrastructure.database.models import AuditEventModel
from vaultlog.infrastructure.security.vault_crypto import (
    AesGcmSecretEncryptor,
    LocalKEKProvider,
)
from vaultlog.shared.config import get_settings

settings = get_settings()


def _secret_use_cases(app_engine, tenant_id: uuid.UUID):
    factory = tenant_uow_factory(app_engine, tenant_id)
    record_denial = record_access_denial(app_engine, tenant_id)
    kek = LocalKEKProvider(settings)
    encryptor = AesGcmSecretEncryptor()
    return (
        CreateSecret(factory, kek, encryptor, record_denial),
        RevealSecret(factory, kek, encryptor, record_denial),
        RotateSecret(factory, kek, encryptor, record_denial),
    )


@pytest.fixture()
async def rbac_tenant(owner_engine, app_engine):
    await seed_rbac_tenant(owner_engine, app_engine)


async def test_rotate_writes_audit_and_chain_verifies(app_engine, rbac_tenant) -> None:
    create, _reveal, rotate = _secret_use_cases(app_engine, ORG_ID)
    actor = make_actor(ADMIN_USER, ORG_ID)
    meta = await create.execute(actor, VAULT_ID, "audit-key", "v1", None)
    await rotate.execute(actor, VAULT_ID, meta.id, "v2")

    verifier = VerifyTenantChain(tenant_uow_factory(app_engine, ORG_ID))
    result = await verifier.execute(ORG_ID)
    assert result.ok
    assert result.events_checked >= 2


async def test_audit_rolls_back_with_failed_mutation(app_engine, rbac_tenant) -> None:
    create, _, rotate = _secret_use_cases(app_engine, ORG_ID)
    actor = make_actor(ADMIN_USER, ORG_ID)
    meta = await create.execute(actor, VAULT_ID, "rollback", "v1", None)

    with (
        patch(
            "vaultlog.infrastructure.database.repositories.secrets.SqlAlchemySecretRepository.update_current_version",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await rotate.execute(actor, VAULT_ID, meta.id, "v2")

    async with tenant_uow_factory(app_engine, ORG_ID)() as uow:
        rows = await uow.audit.list_all_ordered(ORG_ID)
        assert all(row.action != "secret.rotated" for row in rows)


async def test_audit_event_is_immutable_for_app_role(app_engine, rbac_tenant) -> None:
    create, _, _ = _secret_use_cases(app_engine, ORG_ID)
    actor = make_actor(ADMIN_USER, ORG_ID)
    await create.execute(actor, VAULT_ID, "immutable", "v1", None)

    async with tenant_uow_factory(app_engine, ORG_ID)() as uow:
        row = (
            await uow.session.scalars(
                select(AuditEventModel).where(AuditEventModel.tenant_id == ORG_ID)
            )
        ).first()
        assert row is not None

        with pytest.raises(DBAPIError):
            await uow.session.execute(
                text("UPDATE audit_event SET outcome = 'failure' WHERE id = :id"),
                {"id": row.id},
            )
        with pytest.raises(DBAPIError):
            await uow.session.execute(
                text("DELETE FROM audit_event WHERE id = :id"),
                {"id": row.id},
            )


async def test_tamper_detection_content_edit(owner_engine, app_engine, rbac_tenant) -> None:
    create, _, _ = _secret_use_cases(app_engine, ORG_ID)
    actor = make_actor(ADMIN_USER, ORG_ID)
    await create.execute(actor, VAULT_ID, "tamper", "v1", None)

    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                """
                UPDATE audit_event
                SET metadata = '{"tampered": true}'::jsonb
                WHERE tenant_id = :tenant_id AND sequence = 1
                """
            ),
            {"tenant_id": ORG_ID},
        )

    verifier = VerifyTenantChain(tenant_uow_factory(app_engine, ORG_ID))
    result = await verifier.execute(ORG_ID)
    assert result.ok is False
    assert result.reason == "entry_hash mismatch — content altered"


async def test_concurrent_reveals_produce_gapless_chain(app_engine, rbac_tenant) -> None:
    create, reveal, _ = _secret_use_cases(app_engine, ORG_ID)
    actor = make_actor(ADMIN_USER, ORG_ID)
    meta = await create.execute(actor, VAULT_ID, "concurrent", "value", None)

    async def _reveal_once() -> None:
        await reveal.execute(actor, VAULT_ID, meta.id, None)

    await asyncio.gather(*[_reveal_once() for _ in range(20)])

    async with tenant_uow_factory(app_engine, ORG_ID)() as uow:
        events = await uow.audit.list_all_ordered(ORG_ID)
        reveal_events = [event for event in events if event.action == "secret.revealed"]
        sequences = sorted(event.sequence for event in reveal_events)
        assert sequences == list(range(sequences[0], sequences[0] + 20))

    verifier = VerifyTenantChain(tenant_uow_factory(app_engine, ORG_ID))
    assert (await verifier.execute(ORG_ID)).ok


async def test_metadata_guard_raises(app_engine, rbac_tenant) -> None:
    async with tenant_uow_factory(app_engine, ORG_ID)() as uow:
        service = AuditService(uow.audit)
        with pytest.raises(AuditMetadataError):
            await service.record(
                actor=make_actor(ADMIN_USER, ORG_ID),
                action="secret.revealed",
                target_type="secret",
                target_id=uuid.uuid4(),
                metadata={"value": "hunter2"},
            )


async def test_denial_is_recorded_in_separate_transaction(app_engine, rbac_tenant) -> None:
    create, _reveal, _ = _secret_use_cases(app_engine, ORG_ID)

    viewer_actor = make_actor(VIEWER_USER, ORG_ID)
    with pytest.raises(ForbiddenError):
        await create.execute(viewer_actor, VAULT_ID, "deny", "v1", None)

    async with tenant_uow_factory(app_engine, ORG_ID)() as uow:
        events = await uow.audit.list_all_ordered(ORG_ID)
        denied = [event for event in events if event.action == "access.denied"]
        assert len(denied) == 1
        assert denied[0].outcome == "denied"

    verifier = VerifyTenantChain(tenant_uow_factory(app_engine, ORG_ID))
    assert (await verifier.execute(ORG_ID)).ok


async def test_list_audit_events_requires_admin(app_engine, rbac_tenant) -> None:
    list_events = ListAuditEvents(tenant_uow_factory(app_engine, ORG_ID))
    with pytest.raises(ForbiddenError):
        await list_events.execute(make_actor(MEMBER_USER, ORG_ID))

    events = await list_events.execute(make_actor(OWNER_USER, ORG_ID))
    assert isinstance(events, list)


async def test_list_audit_events_enriches_actor(app_engine, rbac_tenant) -> None:
    create, _, _ = _secret_use_cases(app_engine, ORG_ID)
    await create.execute(make_actor(ADMIN_USER, ORG_ID), VAULT_ID, "actor-enrich", "v1", None)

    list_events = ListAuditEvents(tenant_uow_factory(app_engine, ORG_ID))
    events = await list_events.execute(make_actor(OWNER_USER, ORG_ID))

    created = next(event for event in events if event.action == "secret.created")
    assert created.actor is not None
    assert created.actor.email == "admin@rbac.test"
    assert created.actor.role == "admin"
    assert created.actor.status.value == "active"


async def test_cross_tenant_audit_isolation(app_engine, owner_engine, rbac_tenant) -> None:
    from tests.integration.fixtures.constants import TENANT_B

    create, _, _ = _secret_use_cases(app_engine, ORG_ID)
    await create.execute(make_actor(ADMIN_USER, ORG_ID), VAULT_ID, "iso", "v1", None)

    async with tenant_uow_factory(app_engine, TENANT_B)() as uow:
        events = await uow.audit.list_all_ordered(TENANT_B)
        assert events == []

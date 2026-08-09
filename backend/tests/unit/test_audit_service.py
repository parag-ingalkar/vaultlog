from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from vaultlog.domain.audit.exceptions import AuditMetadataError, UnknownAuditActionError
from vaultlog.domain.audit.models import ActorContext, AuditEvent, ChainHead
from vaultlog.domain.audit.services import AuditService

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
SESSION_ID = uuid.uuid4()
VAULT_ID = uuid.uuid4()


class FakeAuditLedger:
    def __init__(self) -> None:
        self.head = ChainHead(tenant_id=TENANT_ID, last_sequence=0, last_hash=None)
        self.events: list[AuditEvent] = []

    async def lock_or_create_head(self, tenant_id: uuid.UUID) -> ChainHead:
        assert tenant_id == TENANT_ID
        return self.head

    async def insert_event(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def advance_head(
        self,
        tenant_id: uuid.UUID,
        *,
        last_sequence: int,
        last_hash: bytes,
    ) -> None:
        self.head = ChainHead(
            tenant_id=tenant_id,
            last_sequence=last_sequence,
            last_hash=last_hash,
        )

    async def list_events(self, tenant_id: uuid.UUID, **kwargs) -> list[AuditEvent]:
        return list(reversed(self.events))

    async def list_all_ordered(self, tenant_id: uuid.UUID) -> list[AuditEvent]:
        return list(self.events)

    async def get_head(self, tenant_id: uuid.UUID) -> ChainHead | None:
        return self.head


def _actor() -> ActorContext:
    return ActorContext(user_id=USER_ID, session_id=SESSION_ID, tenant_id=TENANT_ID)


@pytest.mark.asyncio
async def test_record_unknown_action_raises() -> None:
    service = AuditService(FakeAuditLedger())
    with pytest.raises(UnknownAuditActionError):
        await service.record(
            actor=_actor(),
            action="not.real",
            target_type="vault",
            target_id=VAULT_ID,
        )


@pytest.mark.asyncio
async def test_record_rejects_forbidden_metadata() -> None:
    service = AuditService(FakeAuditLedger())
    with pytest.raises(AuditMetadataError):
        await service.record(
            actor=_actor(),
            action="secret.revealed",
            target_type="secret",
            target_id=VAULT_ID,
            metadata={"value": "hunter2"},
        )


@pytest.mark.asyncio
async def test_record_rejects_nested_forbidden_metadata() -> None:
    service = AuditService(FakeAuditLedger())
    with pytest.raises(AuditMetadataError):
        await service.record(
            actor=_actor(),
            action="secret.revealed",
            target_type="secret",
            target_id=VAULT_ID,
            metadata={"debug": {"password": "x"}},
        )


@pytest.mark.asyncio
async def test_record_appends_sequential_events() -> None:
    ledger = FakeAuditLedger()
    service = AuditService(ledger)
    actor = _actor()

    await service.record(
        actor=actor,
        action="vault.created",
        target_type="vault",
        target_id=VAULT_ID,
    )
    await service.record(
        actor=actor,
        action="vault.updated",
        target_type="vault",
        target_id=VAULT_ID,
    )

    assert len(ledger.events) == 2
    assert ledger.events[0].sequence == 1
    assert ledger.events[1].sequence == 2
    assert ledger.events[1].previous_hash == ledger.events[0].entry_hash
    assert AuditService.verify_chain(ledger.events, ledger.head).ok


def test_verify_chain_detects_content_tamper() -> None:
    occurred = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    event = AuditEvent(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        sequence=1,
        actor_user_id=USER_ID,
        session_id=SESSION_ID,
        action="vault.created",
        target_type="vault",
        target_id=VAULT_ID,
        outcome="success",
        metadata={},
        occurred_at=occurred,
        previous_hash=None,
        entry_hash=b"\x01" * 32,
    )
    head = ChainHead(tenant_id=TENANT_ID, last_sequence=1, last_hash=event.entry_hash)
    result = AuditService.verify_chain([event], head)
    assert result.ok is False
    assert result.reason == "entry_hash mismatch — content altered"


@pytest.mark.asyncio
async def test_verify_chain_detects_head_mismatch() -> None:
    ledger = FakeAuditLedger()
    service = AuditService(ledger)
    await service.record(
        actor=_actor(),
        action="vault.created",
        target_type="vault",
        target_id=VAULT_ID,
    )
    bad_head = ChainHead(tenant_id=TENANT_ID, last_sequence=99, last_hash=b"\x00" * 32)
    result = AuditService.verify_chain(ledger.events, bad_head)
    assert result.ok is False
    assert result.reason == "chain head inconsistent with events"

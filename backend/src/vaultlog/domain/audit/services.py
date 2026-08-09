from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from vaultlog.domain.audit.exceptions import AuditMetadataError, UnknownAuditActionError
from vaultlog.domain.audit.hashing import canonical_event_bytes, compute_entry_hash
from vaultlog.domain.audit.models import (
    ActorContext,
    AuditEvent,
    AuditEventView,
    AuditOutcome,
    ChainHead,
    VerificationResult,
)
from vaultlog.domain.audit.ports import AuditLedgerPort
from vaultlog.domain.audit.vocabulary import AUDIT_ACTIONS, FORBIDDEN_METADATA_KEYS


def _walk_keys(doc: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key, value in doc.items():
        keys.append(str(key))
        if isinstance(value, dict):
            keys.extend(_walk_keys(value))
    return keys


def to_event_view(event: AuditEvent) -> AuditEventView:
    return AuditEventView(
        id=event.id,
        tenant_id=event.tenant_id,
        sequence=event.sequence,
        actor_user_id=event.actor_user_id,
        session_id=event.session_id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        outcome=event.outcome,
        metadata=event.metadata,
        occurred_at=event.occurred_at,
    )


class AuditService:
    def __init__(self, ledger: AuditLedgerPort) -> None:
        self._ledger = ledger

    async def record(
        self,
        *,
        actor: ActorContext,
        action: str,
        target_type: str,
        target_id: uuid.UUID | None = None,
        outcome: str = AuditOutcome.SUCCESS,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if action not in AUDIT_ACTIONS:
            raise UnknownAuditActionError(f"Unknown audit action: {action}")

        safe_metadata = metadata or {}
        offending = FORBIDDEN_METADATA_KEYS & {k.lower() for k in _walk_keys(safe_metadata)}
        if offending:
            raise AuditMetadataError(f"Forbidden audit metadata keys: {sorted(offending)}")

        head = await self._ledger.lock_or_create_head(actor.tenant_id)
        sequence = head.last_sequence + 1
        occurred_at = datetime.now(UTC)

        canonical = canonical_event_bytes(
            tenant_id=actor.tenant_id,
            sequence=sequence,
            actor_user_id=actor.user_id,
            session_id=actor.session_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            metadata=safe_metadata,
            occurred_at=occurred_at,
        )
        entry_hash = compute_entry_hash(head.last_hash, canonical)

        event = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=actor.tenant_id,
            sequence=sequence,
            actor_user_id=actor.user_id,
            session_id=actor.session_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            metadata=safe_metadata,
            occurred_at=occurred_at,
            previous_hash=head.last_hash,
            entry_hash=entry_hash,
        )
        await self._ledger.insert_event(event)
        await self._ledger.advance_head(
            actor.tenant_id,
            last_sequence=sequence,
            last_hash=entry_hash,
        )

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        *,
        action: str | None = None,
        target_id: uuid.UUID | None = None,
        before_sequence: int | None = None,
        limit: int = 100,
    ) -> list[AuditEventView]:
        rows = await self._ledger.list_events(
            tenant_id,
            action=action,
            target_id=target_id,
            before_sequence=before_sequence,
            limit=limit,
        )
        return [to_event_view(row) for row in rows]

    @staticmethod
    def verify_chain(events: list[AuditEvent], head: ChainHead | None) -> VerificationResult:
        expected_previous: bytes | None = None
        expected_sequence = 1

        for row in events:
            if row.sequence != expected_sequence:
                return VerificationResult(
                    ok=False,
                    events_checked=expected_sequence - 1,
                    failure_sequence=row.sequence,
                    reason=f"sequence gap: expected {expected_sequence}, found {row.sequence}",
                )

            if row.previous_hash != expected_previous:
                return VerificationResult(
                    ok=False,
                    events_checked=row.sequence - 1,
                    failure_sequence=row.sequence,
                    reason="previous_hash link broken",
                )

            recomputed = compute_entry_hash(
                expected_previous,
                canonical_event_bytes(
                    tenant_id=row.tenant_id,
                    sequence=row.sequence,
                    actor_user_id=row.actor_user_id,
                    session_id=row.session_id,
                    action=row.action,
                    target_type=row.target_type,
                    target_id=row.target_id,
                    outcome=row.outcome,
                    metadata=row.metadata,
                    occurred_at=row.occurred_at,
                ),
            )
            if recomputed != row.entry_hash:
                return VerificationResult(
                    ok=False,
                    events_checked=row.sequence - 1,
                    failure_sequence=row.sequence,
                    reason="entry_hash mismatch — content altered",
                )

            expected_previous = row.entry_hash
            expected_sequence += 1

        if head is not None and (
            head.last_hash != expected_previous or head.last_sequence != expected_sequence - 1
        ):
            return VerificationResult(
                ok=False,
                events_checked=expected_sequence - 1,
                failure_sequence=None,
                reason="chain head inconsistent with events",
            )

        return VerificationResult(ok=True, events_checked=expected_sequence - 1)

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.audit.models import AuditEvent, ChainHead
from vaultlog.infrastructure.database.models import AuditChainHeadModel, AuditEventModel


def _to_event(row: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        tenant_id=row.tenant_id,
        sequence=row.sequence,
        actor_user_id=row.actor_user_id,
        session_id=row.session_id,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        outcome=row.outcome,
        metadata=row.event_metadata,
        occurred_at=row.occurred_at,
        previous_hash=row.previous_hash,
        entry_hash=row.entry_hash,
    )


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_or_create_head(self, tenant_id: uuid.UUID) -> ChainHead:
        row = await self._session.scalar(
            select(AuditChainHeadModel)
            .where(AuditChainHeadModel.tenant_id == tenant_id)
            .with_for_update()
        )
        if row is None:
            row = AuditChainHeadModel(tenant_id=tenant_id, last_sequence=0, last_hash=None)
            self._session.add(row)
            await self._session.flush()
        return ChainHead(
            tenant_id=row.tenant_id,
            last_sequence=row.last_sequence,
            last_hash=row.last_hash,
        )

    async def insert_event(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventModel(
                id=event.id,
                tenant_id=event.tenant_id,
                sequence=event.sequence,
                actor_user_id=event.actor_user_id,
                session_id=event.session_id,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                outcome=event.outcome,
                event_metadata=event.metadata,
                occurred_at=event.occurred_at,
                previous_hash=event.previous_hash,
                entry_hash=event.entry_hash,
            )
        )

    async def advance_head(
        self,
        tenant_id: uuid.UUID,
        *,
        last_sequence: int,
        last_hash: bytes,
    ) -> None:
        row = await self._session.scalar(
            select(AuditChainHeadModel).where(AuditChainHeadModel.tenant_id == tenant_id)
        )
        if row is None:
            raise RuntimeError("audit chain head missing after lock")
        row.last_sequence = last_sequence
        row.last_hash = last_hash

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        *,
        action: str | None = None,
        target_id: uuid.UUID | None = None,
        before_sequence: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.tenant_id == tenant_id)
            .order_by(AuditEventModel.sequence.desc())
            .limit(limit)
        )
        if action is not None:
            stmt = stmt.where(AuditEventModel.action == action)
        if target_id is not None:
            stmt = stmt.where(AuditEventModel.target_id == target_id)
        if before_sequence is not None:
            stmt = stmt.where(AuditEventModel.sequence < before_sequence)
        rows = (await self._session.scalars(stmt)).all()
        return [_to_event(row) for row in rows]

    async def list_all_ordered(self, tenant_id: uuid.UUID) -> list[AuditEvent]:
        rows = (
            await self._session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.tenant_id == tenant_id)
                .order_by(AuditEventModel.sequence)
            )
        ).all()
        return [_to_event(row) for row in rows]

    async def get_head(self, tenant_id: uuid.UUID) -> ChainHead | None:
        row = await self._session.scalar(
            select(AuditChainHeadModel).where(AuditChainHeadModel.tenant_id == tenant_id)
        )
        if row is None:
            return None
        return ChainHead(
            tenant_id=row.tenant_id,
            last_sequence=row.last_sequence,
            last_hash=row.last_hash,
        )

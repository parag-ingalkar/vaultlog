from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from vaultlog.application.audit.use_cases import ListAuditEvents
from vaultlog.presentation.dependencies import (
    Principal,
    current_principal,
    get_list_audit_events,
)

router = APIRouter(prefix="/audit-events", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    sequence: int
    actor_user_id: uuid.UUID | None
    session_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    outcome: str
    metadata: dict[str, Any]
    occurred_at: str


@router.get("", response_model=list[AuditEventResponse])
async def list_audit_events(
    action: str | None = None,
    target_id: uuid.UUID | None = None,
    before_sequence: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(current_principal),
    use_case: ListAuditEvents = Depends(get_list_audit_events),
) -> list[AuditEventResponse]:
    events = await use_case.execute(
        principal.to_actor(),
        action=action,
        target_id=target_id,
        before_sequence=before_sequence,
        limit=limit,
    )
    return [
        AuditEventResponse(
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
            occurred_at=event.occurred_at.isoformat(),
        )
        for event in events
    ]

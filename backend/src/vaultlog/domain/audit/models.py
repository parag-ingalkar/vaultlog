from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditActorStatus(StrEnum):
    ACTIVE = "active"
    FORMER_MEMBER = "former_member"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ActorContext:
    user_id: uuid.UUID
    session_id: uuid.UUID
    tenant_id: uuid.UUID


@dataclass(frozen=True)
class ChainHead:
    tenant_id: uuid.UUID
    last_sequence: int
    last_hash: bytes | None


@dataclass(frozen=True)
class AuditEvent:
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
    occurred_at: datetime
    previous_hash: bytes | None
    entry_hash: bytes


@dataclass(frozen=True)
class AuditActorView:
    user_id: uuid.UUID
    email: str | None
    role: str | None
    status: AuditActorStatus


@dataclass(frozen=True)
class AuditEventView:
    """API/read-model surface without hash fields."""

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
    occurred_at: datetime
    actor: AuditActorView | None = None


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    events_checked: int
    failure_sequence: int | None = None
    reason: str | None = None

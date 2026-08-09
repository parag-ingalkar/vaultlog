from __future__ import annotations

import uuid
from typing import Protocol

from vaultlog.domain.audit.models import AuditEvent, ChainHead


class AuditLedgerPort(Protocol):
    async def lock_or_create_head(self, tenant_id: uuid.UUID) -> ChainHead: ...

    async def insert_event(self, event: AuditEvent) -> None: ...

    async def advance_head(
        self,
        tenant_id: uuid.UUID,
        *,
        last_sequence: int,
        last_hash: bytes,
    ) -> None: ...

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        *,
        action: str | None = None,
        target_id: uuid.UUID | None = None,
        before_sequence: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]: ...

    async def list_all_ordered(self, tenant_id: uuid.UUID) -> list[AuditEvent]: ...

    async def get_head(self, tenant_id: uuid.UUID) -> ChainHead | None: ...

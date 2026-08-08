from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Vault:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

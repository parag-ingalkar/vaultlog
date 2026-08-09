from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

GENESIS_DOMAIN = b"vaultlog:audit:genesis:v1"


def canonical_event_bytes(
    *,
    tenant_id: UUID,
    sequence: int,
    actor_user_id: UUID | None,
    session_id: UUID | None,
    action: str,
    target_type: str,
    target_id: UUID | None,
    outcome: str,
    metadata: dict[str, Any],
    occurred_at: datetime,
) -> bytes:
    """Byte-stable encoding of an event. Verifier MUST use this same function."""
    doc = {
        "tenant_id": str(tenant_id),
        "sequence": sequence,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "session_id": str(session_id) if session_id else None,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "outcome": outcome,
        "metadata": metadata,
        "occurred_at": occurred_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_entry_hash(previous_hash: bytes | None, canonical: bytes) -> bytes:
    prev = previous_hash if previous_hash is not None else GENESIS_DOMAIN
    return hashlib.sha256(prev + canonical).digest()

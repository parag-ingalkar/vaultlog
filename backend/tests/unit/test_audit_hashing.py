from __future__ import annotations

import uuid
from datetime import UTC, datetime

from vaultlog.domain.audit.hashing import canonical_event_bytes, compute_entry_hash

T = uuid.UUID("11111111-1111-1111-1111-111111111111")
U = uuid.UUID("22222222-2222-2222-2222-222222222222")
S = uuid.UUID("33333333-3333-3333-3333-333333333333")
X = uuid.UUID("44444444-4444-4444-4444-444444444444")
AT = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _canonical(**overrides):
    kwargs = dict(
        tenant_id=T,
        sequence=1,
        actor_user_id=U,
        session_id=S,
        action="secret.revealed",
        target_type="secret",
        target_id=X,
        outcome="success",
        metadata={"version": 3},
        occurred_at=AT,
    )
    kwargs.update(overrides)
    return canonical_event_bytes(**kwargs)


def test_golden_vector() -> None:
    assert _canonical() == (
        b'{"action":"secret.revealed","actor_user_id":"22222222-2222-2222-2222-222222222222",'
        b'"metadata":{"version":3},"occurred_at":"2026-07-29T12:00:00.000000Z",'
        b'"outcome":"success","sequence":1,"session_id":"33333333-3333-3333-3333-333333333333",'
        b'"target_id":"44444444-4444-4444-4444-444444444444","target_type":"secret",'
        b'"tenant_id":"11111111-1111-1111-1111-111111111111"}'
    )


def test_key_order_is_canonical() -> None:
    a = canonical_event_bytes(
        tenant_id=T,
        sequence=1,
        actor_user_id=None,
        session_id=None,
        action="vault.created",
        target_type="vault",
        target_id=None,
        outcome="success",
        metadata={"b": 2, "a": 1},
        occurred_at=AT,
    )
    b = canonical_event_bytes(
        tenant_id=T,
        sequence=1,
        actor_user_id=None,
        session_id=None,
        action="vault.created",
        target_type="vault",
        target_id=None,
        outcome="success",
        metadata={"a": 1, "b": 2},
        occurred_at=AT,
    )
    assert a == b


def test_genesis_differs_from_chained() -> None:
    canonical = _canonical()
    assert compute_entry_hash(None, canonical) != compute_entry_hash(b"\x00" * 32, canonical)

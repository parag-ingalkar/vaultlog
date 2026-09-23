from __future__ import annotations

import uuid
from datetime import UTC, datetime

from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.audit.enrichment import build_actor_view, enrich_events_with_actors
from vaultlog.domain.audit.models import AuditActorStatus, AuditEventView

USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
EVENT_ID = uuid.uuid4()
NOW = datetime.now(UTC)


def _event(actor_user_id: uuid.UUID | None = USER_ID) -> AuditEventView:
    return AuditEventView(
        id=EVENT_ID,
        tenant_id=TENANT_ID,
        sequence=1,
        actor_user_id=actor_user_id,
        session_id=uuid.uuid4(),
        action="secret.revealed",
        target_type="secret",
        target_id=uuid.uuid4(),
        outcome="success",
        metadata={},
        occurred_at=NOW,
    )


def test_build_actor_view_active() -> None:
    actor = build_actor_view(USER_ID, email="alice@example.com", role=OrgRole.ADMIN)
    assert actor.status is AuditActorStatus.ACTIVE
    assert actor.email == "alice@example.com"
    assert actor.role == "admin"


def test_build_actor_view_former_member() -> None:
    actor = build_actor_view(USER_ID, email="alice@example.com", role=None)
    assert actor.status is AuditActorStatus.FORMER_MEMBER
    assert actor.role is None


def test_build_actor_view_unknown() -> None:
    actor = build_actor_view(USER_ID, email=None, role=None)
    assert actor.status is AuditActorStatus.UNKNOWN
    assert actor.email is None


def test_enrich_events_with_actors() -> None:
    actor = build_actor_view(USER_ID, email="alice@example.com", role=OrgRole.OWNER)
    enriched = enrich_events_with_actors([_event()], {USER_ID: actor})
    assert enriched[0].actor == actor


def test_enrich_events_without_actor_user_id() -> None:
    event = _event(actor_user_id=None)
    enriched = enrich_events_with_actors([event], {})
    assert enriched[0].actor is None


def test_enrich_events_missing_lookup_is_unknown() -> None:
    enriched = enrich_events_with_actors([_event()], {})
    assert enriched[0].actor is not None
    assert enriched[0].actor.status is AuditActorStatus.UNKNOWN

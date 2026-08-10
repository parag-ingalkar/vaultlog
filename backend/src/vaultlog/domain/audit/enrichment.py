from __future__ import annotations

import uuid
from dataclasses import replace

from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.audit.models import AuditActorStatus, AuditActorView, AuditEventView


def build_actor_view(
    user_id: uuid.UUID,
    *,
    email: str | None,
    role: OrgRole | None,
) -> AuditActorView:
    if email is None:
        status = AuditActorStatus.UNKNOWN
    elif role is not None:
        status = AuditActorStatus.ACTIVE
    else:
        status = AuditActorStatus.FORMER_MEMBER
    return AuditActorView(
        user_id=user_id,
        email=email,
        role=role.value if role is not None else None,
        status=status,
    )


def enrich_events_with_actors(
    events: list[AuditEventView],
    actors: dict[uuid.UUID, AuditActorView],
) -> list[AuditEventView]:
    enriched: list[AuditEventView] = []
    for event in events:
        if event.actor_user_id is None:
            enriched.append(event)
            continue
        actor = actors.get(event.actor_user_id)
        if actor is None:
            actor = build_actor_view(event.actor_user_id, email=None, role=None)
        enriched.append(replace(event, actor=actor))
    return enriched

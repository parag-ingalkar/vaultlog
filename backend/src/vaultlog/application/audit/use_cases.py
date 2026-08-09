from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from vaultlog.application.audit.helpers import build_audit_service
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.access.models import Action
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.audit.models import (
    ActorContext,
    AuditEventView,
    AuditOutcome,
    VerificationResult,
)
from vaultlog.domain.audit.services import AuditService


def build_policy_service(uow: TenantUnitOfWork) -> PolicyService:
    return PolicyService(
        memberships=uow.membership_access,
        vaults=uow.vault_access,
        grants=uow.grant_access,
    )


class RecordAccessDenial:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, actor: ActorContext, exc: ForbiddenError) -> None:
        if not exc.audit_denial:
            return

        metadata: dict[str, Any] = {}
        if exc.attempted_action is not None:
            metadata["attempted_action"] = exc.attempted_action

        async with self._uow_factory() as uow:
            audit = build_audit_service(uow)
            await audit.record(
                actor=actor,
                action="access.denied",
                target_type=exc.audit_target_type or "vault",
                target_id=exc.audit_target_id,
                outcome=AuditOutcome.DENIED,
                metadata=metadata,
            )
            await uow.commit()


async def record_denial_if_needed(
    record_denial: RecordAccessDenial,
    actor: ActorContext,
    exc: ForbiddenError,
) -> None:
    if exc.audit_denial:
        await record_denial.execute(actor, exc)


class ListAuditEvents:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        actor: ActorContext,
        *,
        action: str | None = None,
        target_id: uuid.UUID | None = None,
        before_sequence: int | None = None,
        limit: int = 100,
    ) -> list[AuditEventView]:
        async with self._uow_factory() as uow:
            policy = build_policy_service(uow)
            await policy.require_org(actor.user_id, actor.tenant_id, Action.AUDIT_READ)
            audit = build_audit_service(uow)
            return await audit.list_events(
                actor.tenant_id,
                action=action,
                target_id=target_id,
                before_sequence=before_sequence,
                limit=limit,
            )


class VerifyTenantChain:
    def __init__(self, uow_factory: Callable[[], TenantUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, tenant_id: uuid.UUID) -> VerificationResult:

        async with self._uow_factory() as uow:
            events = await uow.audit.list_all_ordered(tenant_id)
            head = await uow.audit.get_head(tenant_id)
            return AuditService.verify_chain(events, head)

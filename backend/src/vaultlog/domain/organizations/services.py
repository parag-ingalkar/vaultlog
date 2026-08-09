from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from vaultlog.domain.access.exceptions import ForbiddenError
from vaultlog.domain.access.models import Action, OrgRole
from vaultlog.domain.access.services import PolicyService
from vaultlog.domain.audit.models import ActorContext
from vaultlog.domain.audit.services import AuditService
from vaultlog.domain.organizations.exceptions import (
    InvitationError,
    InvitationNotFoundError,
    MemberConflictError,
    MemberNotFoundError,
)
from vaultlog.domain.organizations.models import (
    Invitation,
    MemberView,
    OrganizationView,
)
from vaultlog.domain.organizations.ports import (
    EmailSender,
    InvitationRepository,
    MemberRepository,
    OrganizationReader,
)

INVITABLE_ROLES = frozenset({OrgRole.ADMIN, OrgRole.MEMBER, OrgRole.VIEWER})
INVITE_TTL_DAYS = 7


def hash_invite_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


class OrganizationService:
    def __init__(
        self,
        *,
        invitations: InvitationRepository,
        members: MemberRepository,
        organizations: OrganizationReader,
        policy: PolicyService,
        audit: AuditService,
        email_sender: EmailSender,
        invite_base_url: str,
    ) -> None:
        self._invitations = invitations
        self._members = members
        self._organizations = organizations
        self._policy = policy
        self._audit = audit
        self._email_sender = email_sender
        self._invite_base_url = invite_base_url.rstrip("/")

    async def get_organization(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> OrganizationView:
        ctx = await self._policy.require_org(user_id, tenant_id, Action.VAULT_LIST)
        name = await self._organizations.get_name(tenant_id)
        if name is None:
            raise MemberNotFoundError("Organization not found")
        return OrganizationView(id=tenant_id, name=name, caller_role=ctx.role)

    async def create_invitation(
        self,
        actor: ActorContext,
        email: str,
        role: OrgRole,
    ) -> tuple[Invitation, str]:
        ctx = await self._policy.require_org(actor.user_id, actor.tenant_id, Action.MEMBER_INVITE)
        inviter_role = ctx.role

        normalized = email.strip().lower()
        if role not in INVITABLE_ROLES:
            raise InvitationError("Invitation failed")
        if inviter_role is OrgRole.ADMIN and role is OrgRole.ADMIN:
            raise InvitationError("Invitation failed")

        if await self._invitations.has_pending_for_email(actor.tenant_id, normalized):
            raise InvitationError("Invitation failed")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_invite_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS)

        invitation = await self._invitations.add(
            tenant_id=actor.tenant_id,
            email=normalized,
            role=role,
            token_hash=token_hash,
            invited_by_user_id=actor.user_id,
            expires_at=expires_at,
        )

        org_name = await self._organizations.get_name(actor.tenant_id)
        if org_name is None:
            raise InvitationError("Invitation failed")

        invite_url = f"{self._invite_base_url}?token={raw_token}"
        await self._email_sender.send_invitation(
            to=normalized,
            invite_url=invite_url,
            organization_name=org_name,
            role=role,
        )

        await self._audit.record(
            actor=actor,
            action="member.invited",
            target_type="invitation",
            target_id=invitation.id,
            outcome="success",
            metadata={"email": normalized, "role": role.value},
        )
        return invitation, raw_token

    async def list_invitations(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[Invitation]:
        await self._policy.require_org(user_id, tenant_id, Action.MEMBER_INVITE)
        return await self._invitations.list_pending(tenant_id)

    async def revoke_invitation(
        self,
        actor: ActorContext,
        invitation_id: uuid.UUID,
    ) -> None:
        await self._policy.require_org(actor.user_id, actor.tenant_id, Action.MEMBER_INVITE)
        invitation = await self._invitations.get_by_id(invitation_id, actor.tenant_id)
        if (
            invitation is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
        ):
            raise InvitationNotFoundError("Invitation not found")
        await self._invitations.mark_revoked(
            invitation_id,
            actor.tenant_id,
            revoked_at=datetime.now(UTC),
        )

    async def list_members(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[MemberView]:
        await self._policy.require_org(user_id, tenant_id, Action.MEMBER_INVITE)
        return await self._members.list_members(tenant_id)

    async def remove_member(
        self,
        actor: ActorContext,
        membership_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        if not step_up_proven:
            raise ForbiddenError("Step-up authentication required")
        ctx = await self._policy.require_org(actor.user_id, actor.tenant_id, Action.MEMBER_REMOVE)
        actor_role = ctx.role

        target = await self._members.get_by_id(membership_id, actor.tenant_id)
        if target is None:
            raise MemberNotFoundError("Member not found")

        if target.user_id == actor.user_id:
            raise MemberConflictError("Cannot remove yourself")

        if target.role is OrgRole.OWNER:
            raise MemberConflictError("Cannot remove owner")

        if actor_role is OrgRole.ADMIN and target.role in (OrgRole.OWNER, OrgRole.ADMIN):
            raise MemberConflictError("Cannot remove this member")

        removed = await self._members.remove(membership_id, actor.tenant_id)
        if not removed:
            raise MemberNotFoundError("Member not found")

        await self._audit.record(
            actor=actor,
            action="member.removed",
            target_type="membership",
            target_id=membership_id,
            outcome="success",
            metadata={"user_id": str(target.user_id), "role": target.role.value},
        )

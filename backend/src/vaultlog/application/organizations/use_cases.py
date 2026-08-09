from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from vaultlog.application.audit.helpers import build_audit_service
from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.application.vaults.use_cases import build_policy_service
from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.audit.models import ActorContext
from vaultlog.domain.identity.password import validate_password_strength
from vaultlog.domain.identity.ports import PasswordHasher
from vaultlog.domain.organizations.exceptions import (
    InvitationError,
    InvitationNotFoundError,
    MemberConflictError,
)
from vaultlog.domain.organizations.models import (
    Invitation,
    InvitationPreview,
    MemberView,
    OrganizationView,
)
from vaultlog.domain.organizations.ports import EmailSender
from vaultlog.domain.organizations.services import (
    OrganizationService,
    hash_invite_token,
    mask_email,
)


def _build_org_service(
    uow: TenantUnitOfWork, *, invite_base_url: str, email_sender: EmailSender
) -> OrganizationService:
    policy = build_policy_service(uow)
    audit = build_audit_service(uow)
    return OrganizationService(
        invitations=uow.invitations,
        members=uow.members,
        organizations=uow.organizations,
        policy=policy,
        audit=audit,
        email_sender=email_sender,
        invite_base_url=invite_base_url,
    )


class GetOrganization:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(self, actor: ActorContext) -> OrganizationView:
        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            view = await service.get_organization(actor.user_id, actor.tenant_id)
            await uow.commit()
            return view


class CreateInvitation:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        identity_uow_factory: Callable[[], IdentityUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._identity_uow_factory = identity_uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(self, actor: ActorContext, email: str, role: OrgRole) -> Invitation:
        normalized = email.strip().lower()
        async with self._identity_uow_factory() as identity_uow:
            if await identity_uow.memberships.has_membership_for_email(normalized):
                raise InvitationError("Invitation failed")

        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            invitation, _raw = await service.create_invitation(actor, email, role)
            await uow.commit()
            return invitation


class ListInvitations:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[Invitation]:
        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            invitations = await service.list_invitations(user_id, tenant_id)
            await uow.commit()
            return invitations


class RevokeInvitation:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(self, actor: ActorContext, invitation_id: uuid.UUID) -> None:
        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            await service.revoke_invitation(actor, invitation_id)
            await uow.commit()


class PreviewInvitation:
    def __init__(self, identity_uow_factory: Callable[[], IdentityUnitOfWork]) -> None:
        self._identity_uow_factory = identity_uow_factory

    async def execute(self, raw_token: str) -> InvitationPreview:
        token_hash = hash_invite_token(raw_token)
        async with self._identity_uow_factory() as uow:
            lookup = uow.invitation_lookup
            invitation = await lookup.get_pending_by_token_hash(token_hash)
            if invitation is None:
                raise InvitationNotFoundError("Invitation not found")
            if invitation.expires_at <= datetime.now(UTC):
                raise InvitationNotFoundError("Invitation not found")

            org_name = await lookup.get_organization_name(invitation.tenant_id)
            if org_name is None:
                raise InvitationNotFoundError("Invitation not found")

            return InvitationPreview(
                organization_name=org_name,
                role=invitation.role,
                email_masked=mask_email(invitation.email),
            )


class AcceptInvitation:
    def __init__(
        self,
        tenant_uow_factory: Callable[[uuid.UUID], TenantUnitOfWork],
        identity_uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
    ) -> None:
        self._tenant_uow_factory = tenant_uow_factory
        self._identity_uow_factory = identity_uow_factory
        self._passwords = passwords

    async def execute(self, raw_token: str, password: str) -> None:
        token_hash = hash_invite_token(raw_token)
        async with self._identity_uow_factory() as identity_uow:
            lookup = identity_uow.invitation_lookup
            invitation = await lookup.get_pending_by_token_hash(token_hash)
            if invitation is None:
                raise InvitationNotFoundError("Invitation not found")
            if invitation.expires_at <= datetime.now(UTC):
                raise InvitationNotFoundError("Invitation not found")

            if await identity_uow.memberships.has_membership_for_email(invitation.email):
                raise MemberConflictError("Invitation failed")

            user = await identity_uow.users.get_by_email(invitation.email)
            if user is None:
                validate_password_strength(password)
                user = await identity_uow.users.add(
                    invitation.email,
                    self._passwords.hash(password),
                )
            elif not self._passwords.verify(password, user.password_hash):
                raise InvitationError("Invitation failed")

            if await identity_uow.memberships.has_membership(user.id):
                raise MemberConflictError("Invitation failed")

            await identity_uow.commit()

        async with self._tenant_uow_factory(invitation.tenant_id) as tenant_uow:
            await tenant_uow.members.add(
                tenant_id=invitation.tenant_id,
                user_id=user.id,
                role=invitation.role,
            )
            await tenant_uow.invitations.mark_accepted(
                invitation.id,
                invitation.tenant_id,
                accepted_at=datetime.now(UTC),
            )
            await tenant_uow.commit()


class ListMembers:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[MemberView]:
        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            members = await service.list_members(user_id, tenant_id)
            await uow.commit()
            return members


class RemoveMember:
    def __init__(
        self,
        uow_factory: Callable[[], TenantUnitOfWork],
        invite_base_url: str,
        email_sender: EmailSender,
    ) -> None:
        self._uow_factory = uow_factory
        self._invite_base_url = invite_base_url
        self._email_sender = email_sender

    async def execute(
        self,
        actor: ActorContext,
        membership_id: uuid.UUID,
        *,
        step_up_proven: bool,
    ) -> None:
        async with self._uow_factory() as uow:
            service = _build_org_service(
                uow,
                invite_base_url=self._invite_base_url,
                email_sender=self._email_sender,
            )
            await service.remove_member(
                actor,
                membership_id,
                step_up_proven=step_up_proven,
            )
            await uow.commit()

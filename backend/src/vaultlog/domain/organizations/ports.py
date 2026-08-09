from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.organizations.models import Invitation, MemberView


class InvitationRepository(Protocol):
    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        role: OrgRole,
        token_hash: str,
        invited_by_user_id: uuid.UUID,
        expires_at: datetime,
    ) -> Invitation: ...

    async def get_by_id(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Invitation | None: ...

    async def get_pending_by_token_hash(self, token_hash: str) -> Invitation | None: ...

    async def has_pending_for_email(self, tenant_id: uuid.UUID, email: str) -> bool: ...

    async def list_pending(self, tenant_id: uuid.UUID) -> list[Invitation]: ...

    async def mark_accepted(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID, *, accepted_at: datetime
    ) -> None: ...

    async def mark_revoked(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID, *, revoked_at: datetime
    ) -> None: ...


class MemberRepository(Protocol):
    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role: OrgRole,
    ) -> uuid.UUID: ...

    async def list_members(self, tenant_id: uuid.UUID) -> list[MemberView]: ...

    async def get_by_id(
        self, membership_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> MemberView | None: ...

    async def remove(self, membership_id: uuid.UUID, tenant_id: uuid.UUID) -> bool: ...

    async def count_by_role(self, tenant_id: uuid.UUID, role: OrgRole) -> int: ...


class OrganizationReader(Protocol):
    async def get_name(self, tenant_id: uuid.UUID) -> str | None: ...


class GlobalMembershipPort(Protocol):
    async def has_membership(self, user_id: uuid.UUID) -> bool: ...

    async def has_membership_for_email(self, email: str) -> bool: ...


class EmailSender(Protocol):
    async def send_invitation(
        self,
        *,
        to: str,
        invite_url: str,
        organization_name: str,
        role: OrgRole,
    ) -> None: ...


class InvitationTokenLookup(Protocol):
    async def get_pending_by_token_hash(self, token_hash: str) -> Invitation | None: ...

    async def get_organization_name(self, tenant_id: uuid.UUID) -> str | None: ...

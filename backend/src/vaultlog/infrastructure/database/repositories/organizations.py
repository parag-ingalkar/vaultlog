from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.organizations.models import Invitation, MemberView
from vaultlog.infrastructure.database.identity_models import MembershipModel, UserModel
from vaultlog.infrastructure.database.models import InvitationModel, OrganizationModel


def _to_invitation(row: InvitationModel) -> Invitation:
    return Invitation(
        id=row.id,
        tenant_id=row.tenant_id,
        email=row.email,
        role=OrgRole(row.role),
        token_hash=row.token_hash,
        invited_by_user_id=row.invited_by_user_id,
        expires_at=row.expires_at,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


class SqlAlchemyInvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        role: OrgRole,
        token_hash: str,
        invited_by_user_id: uuid.UUID,
        expires_at: datetime,
    ) -> Invitation:
        row = InvitationModel(
            tenant_id=tenant_id,
            email=email,
            role=role.value,
            token_hash=token_hash,
            invited_by_user_id=invited_by_user_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_invitation(row)

    async def get_by_id(self, invitation_id: uuid.UUID, tenant_id: uuid.UUID) -> Invitation | None:
        row = await self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.id == invitation_id,
                InvitationModel.tenant_id == tenant_id,
            )
        )
        return _to_invitation(row) if row is not None else None

    async def get_pending_by_token_hash(self, token_hash: str) -> Invitation | None:
        row = await self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.token_hash == token_hash,
                InvitationModel.accepted_at.is_(None),
                InvitationModel.revoked_at.is_(None),
            )
        )
        return _to_invitation(row) if row is not None else None

    async def has_pending_for_email(self, tenant_id: uuid.UUID, email: str) -> bool:
        result = await self._session.scalar(
            select(InvitationModel.id).where(
                InvitationModel.tenant_id == tenant_id,
                InvitationModel.email == email,
                InvitationModel.accepted_at.is_(None),
                InvitationModel.revoked_at.is_(None),
            )
        )
        return result is not None

    async def list_pending(self, tenant_id: uuid.UUID) -> list[Invitation]:
        rows = await self._session.scalars(
            select(InvitationModel)
            .where(
                InvitationModel.tenant_id == tenant_id,
                InvitationModel.accepted_at.is_(None),
                InvitationModel.revoked_at.is_(None),
            )
            .order_by(InvitationModel.created_at.desc())
        )
        return [_to_invitation(row) for row in rows]

    async def mark_accepted(
        self,
        invitation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        accepted_at: datetime,
    ) -> None:
        row = await self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.id == invitation_id,
                InvitationModel.tenant_id == tenant_id,
            )
        )
        if row is not None:
            row.accepted_at = accepted_at

    async def mark_revoked(
        self,
        invitation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        revoked_at: datetime,
    ) -> None:
        row = await self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.id == invitation_id,
                InvitationModel.tenant_id == tenant_id,
            )
        )
        if row is not None:
            row.revoked_at = revoked_at


class SqlAlchemyMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role: OrgRole,
    ) -> uuid.UUID:
        row = MembershipModel(tenant_id=tenant_id, user_id=user_id, role=role.value)
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def list_members(self, tenant_id: uuid.UUID) -> list[MemberView]:
        rows = await self._session.execute(
            select(
                MembershipModel.id,
                MembershipModel.user_id,
                UserModel.email,
                MembershipModel.role,
                MembershipModel.created_at,
            )
            .join(UserModel, UserModel.id == MembershipModel.user_id)
            .where(MembershipModel.tenant_id == tenant_id)
            .order_by(MembershipModel.created_at.asc())
        )
        return [
            MemberView(
                membership_id=row.id,
                user_id=row.user_id,
                email=row.email,
                role=OrgRole(row.role),
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def get_by_id(self, membership_id: uuid.UUID, tenant_id: uuid.UUID) -> MemberView | None:
        row = await self._session.execute(
            select(
                MembershipModel.id,
                MembershipModel.user_id,
                UserModel.email,
                MembershipModel.role,
                MembershipModel.created_at,
            )
            .join(UserModel, UserModel.id == MembershipModel.user_id)
            .where(
                MembershipModel.id == membership_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        result = row.first()
        if result is None:
            return None
        return MemberView(
            membership_id=result.id,
            user_id=result.user_id,
            email=result.email,
            role=OrgRole(result.role),
            created_at=result.created_at,
        )

    async def remove(self, membership_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                delete(MembershipModel).where(
                    MembershipModel.id == membership_id,
                    MembershipModel.tenant_id == tenant_id,
                )
            ),
        )
        return (result.rowcount or 0) > 0

    async def count_by_role(self, tenant_id: uuid.UUID, role: OrgRole) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(MembershipModel)
            .where(
                MembershipModel.tenant_id == tenant_id,
                MembershipModel.role == role.value,
            )
        )
        return int(count or 0)


class SqlAlchemyOrganizationReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_name(self, tenant_id: uuid.UUID) -> str | None:
        result: str | None = await self._session.scalar(
            select(OrganizationModel.name).where(OrganizationModel.id == tenant_id)
        )
        return result


class SqlAlchemyInvitationTokenLookup:
    """Owner-role lookup for invitations by token (pre-tenant / public accept flow)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_by_token_hash(self, token_hash: str) -> Invitation | None:
        row = await self._session.scalar(
            select(InvitationModel).where(
                InvitationModel.token_hash == token_hash,
                InvitationModel.accepted_at.is_(None),
                InvitationModel.revoked_at.is_(None),
            )
        )
        return _to_invitation(row) if row is not None else None

    async def get_organization_name(self, tenant_id: uuid.UUID) -> str | None:
        result: str | None = await self._session.scalar(
            select(OrganizationModel.name).where(OrganizationModel.id == tenant_id)
        )
        return result

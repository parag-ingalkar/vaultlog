from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.access.models import OrgRole, VaultPermission
from vaultlog.domain.access.ports import (
    MembershipAccessPort,
    VaultAccessPort,
    VaultGrantAccessPort,
)
from vaultlog.domain.vaults.models import GrantView, Vault
from vaultlog.domain.vaults.ports import VaultGrantRepository, VaultRepository
from vaultlog.infrastructure.database.identity_models import MembershipModel, UserModel
from vaultlog.infrastructure.database.models import VaultGrantModel, VaultModel


def _to_vault(row: VaultModel) -> Vault:
    return Vault(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyMembershipAccessRepository(MembershipAccessPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_role(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> OrgRole | None:
        role = await self._session.scalar(
            select(MembershipModel.role).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        return OrgRole(role) if role else None

    async def get_membership_id(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID | None:
        value = await self._session.scalar(
            select(MembershipModel.id).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        return value if value is not None else None

    async def get_membership_tenant(self, membership_id: uuid.UUID) -> uuid.UUID | None:
        value = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.id == membership_id)
        )
        return value if value is not None else None


class SqlAlchemyVaultAccessRepository(VaultAccessPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        result = await self._session.scalar(
            select(VaultModel.id).where(
                VaultModel.id == vault_id,
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
        )
        return result is not None


class SqlAlchemyVaultGrantAccessRepository(VaultGrantAccessPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_permission(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
    ) -> VaultPermission | None:
        permission = await self._session.scalar(
            select(VaultGrantModel.permission)
            .join(MembershipModel, MembershipModel.id == VaultGrantModel.membership_id)
            .where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.tenant_id == tenant_id,
                MembershipModel.user_id == user_id,
            )
        )
        return VaultPermission(permission) if permission else None

    async def list_vault_ids_for_user(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        rows = await self._session.scalars(
            select(VaultGrantModel.vault_id)
            .join(MembershipModel, MembershipModel.id == VaultGrantModel.membership_id)
            .where(
                VaultGrantModel.tenant_id == tenant_id,
                MembershipModel.user_id == user_id,
            )
        )
        return list(rows)


class SqlAlchemyVaultRepository(VaultRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by_user_id: uuid.UUID,
    ) -> Vault:
        row = VaultModel(
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_vault(row)

    async def get_active(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> Vault | None:
        row = await self._session.scalar(
            select(VaultModel).where(
                VaultModel.id == vault_id,
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
        )
        return _to_vault(row) if row else None

    async def list_active(
        self,
        tenant_id: uuid.UUID,
        *,
        vault_ids: list[uuid.UUID] | None = None,
    ) -> list[Vault]:
        stmt = (
            select(VaultModel)
            .where(
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
            .order_by(VaultModel.name)
        )
        if vault_ids is not None:
            stmt = stmt.where(VaultModel.id.in_(vault_ids))
        rows = await self._session.scalars(stmt)
        return [_to_vault(row) for row in rows]

    async def soft_delete(self, vault_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        await self._session.execute(
            update(VaultModel)
            .where(
                VaultModel.id == vault_id,
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )

    async def update(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> Vault:
        row = await self._session.scalar(
            select(VaultModel).where(
                VaultModel.id == vault_id,
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
        )
        if row is None:
            raise ValueError("Vault not found")
        if name is not None:
            row.name = name
        if clear_description:
            row.description = None
        elif description is not None:
            row.description = description
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_vault(row)


class SqlAlchemyVaultGrantRepository(VaultGrantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        permission: VaultPermission,
        granted_by_user_id: uuid.UUID,
    ) -> bool:
        existing = await self._session.scalar(
            select(VaultGrantModel).where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.membership_id == membership_id,
            )
        )
        if existing is not None:
            existing.permission = permission.value
            existing.granted_by_user_id = granted_by_user_id
            return False

        self._session.add(
            VaultGrantModel(
                tenant_id=tenant_id,
                vault_id=vault_id,
                membership_id=membership_id,
                permission=permission.value,
                granted_by_user_id=granted_by_user_id,
            )
        )
        return True

    async def delete(
        self,
        vault_id: uuid.UUID,
        membership_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                delete(VaultGrantModel).where(
                    VaultGrantModel.vault_id == vault_id,
                    VaultGrantModel.membership_id == membership_id,
                    VaultGrantModel.tenant_id == tenant_id,
                )
            ),
        )
        return (result.rowcount or 0) > 0

    async def list_for_vault(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[GrantView]:
        rows = await self._session.execute(
            select(
                VaultGrantModel.membership_id,
                MembershipModel.user_id,
                UserModel.email,
                MembershipModel.role,
                VaultGrantModel.permission,
                VaultGrantModel.created_at,
            )
            .join(MembershipModel, MembershipModel.id == VaultGrantModel.membership_id)
            .join(UserModel, UserModel.id == MembershipModel.user_id)
            .where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.tenant_id == tenant_id,
            )
            .order_by(UserModel.email.asc())
        )
        return [
            GrantView(
                membership_id=row.membership_id,
                user_id=row.user_id,
                email=row.email,
                org_role=OrgRole(row.role),
                permission=VaultPermission(row.permission),
                granted_at=row.created_at,
            )
            for row in rows
        ]

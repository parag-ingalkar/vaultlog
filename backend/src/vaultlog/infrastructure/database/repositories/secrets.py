from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.secrets.exceptions import SecretConflictError
from vaultlog.domain.secrets.models import Secret, SecretVersion, TenantKeyVersion
from vaultlog.domain.secrets.ports import (
    SecretRepository,
    SecretVersionRepository,
    TenantKeyRepository,
)
from vaultlog.infrastructure.database.models import (
    SecretModel,
    SecretVersionModel,
    TenantKeyVersionModel,
)


def _to_secret(row: SecretModel) -> Secret:
    return Secret(
        id=row.id,
        tenant_id=row.tenant_id,
        vault_id=row.vault_id,
        name=row.name,
        description=row.description,
        current_version=row.current_version,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _to_version(row: SecretVersionModel) -> SecretVersion:
    return SecretVersion(
        id=row.id,
        tenant_id=row.tenant_id,
        secret_id=row.secret_id,
        version=row.version,
        ciphertext=row.ciphertext,
        nonce=row.nonce,
        dek_version=row.dek_version,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


def _to_key(row: TenantKeyVersionModel) -> TenantKeyVersion:
    return TenantKeyVersion(
        tenant_id=row.tenant_id,
        version=row.version,
        wrapped_dek=row.wrapped_dek,
        wrap_nonce=row.wrap_nonce,
        wrapping_key_id=row.wrapping_key_id,
        status=row.status,
    )


class SqlAlchemyTenantKeyRepository(TenantKeyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self, tenant_id: uuid.UUID) -> TenantKeyVersion | None:
        row = await self._session.scalar(
            select(TenantKeyVersionModel).where(
                TenantKeyVersionModel.tenant_id == tenant_id,
                TenantKeyVersionModel.status == "active",
            )
        )
        return _to_key(row) if row else None

    async def get_by_version(
        self,
        tenant_id: uuid.UUID,
        version: int,
    ) -> TenantKeyVersion | None:
        row = await self._session.scalar(
            select(TenantKeyVersionModel).where(
                TenantKeyVersionModel.tenant_id == tenant_id,
                TenantKeyVersionModel.version == version,
            )
        )
        return _to_key(row) if row else None

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        version: int,
        wrapped_dek: bytes,
        wrap_nonce: bytes,
        wrapping_key_id: str,
        status: str,
    ) -> TenantKeyVersion:
        row = TenantKeyVersionModel(
            tenant_id=tenant_id,
            version=version,
            wrapped_dek=wrapped_dek,
            wrap_nonce=wrap_nonce,
            wrapping_key_id=wrapping_key_id,
            status=status,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SecretConflictError("Tenant key already provisioned") from exc
        await self._session.refresh(row)
        return _to_key(row)


class SqlAlchemySecretRepository(SecretRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by_user_id: uuid.UUID,
        current_version: int,
    ) -> Secret:
        row = SecretModel(
            tenant_id=tenant_id,
            vault_id=vault_id,
            name=name,
            description=description,
            created_by_user_id=created_by_user_id,
            current_version=current_version,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SecretConflictError("Secret name already exists in this vault") from exc
        await self._session.refresh(row)
        return _to_secret(row)

    async def get_active(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None:
        row = await self._session.scalar(
            select(SecretModel).where(
                SecretModel.id == secret_id,
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            )
        )
        return _to_secret(row) if row else None

    async def get_active_for_update(
        self,
        secret_id: uuid.UUID,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Secret | None:
        row = await self._session.scalar(
            select(SecretModel)
            .where(
                SecretModel.id == secret_id,
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return _to_secret(row) if row else None

    async def list_active(
        self,
        vault_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[Secret]:
        rows = await self._session.scalars(
            select(SecretModel)
            .where(
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            )
            .order_by(SecretModel.name)
        )
        return [_to_secret(row) for row in rows]

    async def soft_delete(
        self,
        secret_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(SecretModel)
                .where(
                    SecretModel.id == secret_id,
                    SecretModel.tenant_id == tenant_id,
                    SecretModel.deleted_at.is_(None),
                )
                .values(deleted_at=datetime.now(UTC))
            ),
        )
        return (result.rowcount or 0) > 0

    async def update_current_version(
        self,
        secret_id: uuid.UUID,
        tenant_id: uuid.UUID,
        current_version: int,
    ) -> Secret:
        row = await self._session.scalar(
            select(SecretModel).where(
                SecretModel.id == secret_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            )
        )
        if row is None:
            raise ValueError("Secret not found")
        row.current_version = current_version
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_secret(row)


class SqlAlchemySecretVersionRepository(SecretVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        tenant_id: uuid.UUID,
        secret_id: uuid.UUID,
        version: int,
        ciphertext: bytes,
        nonce: bytes,
        dek_version: int,
        created_by_user_id: uuid.UUID,
    ) -> SecretVersion:
        row = SecretVersionModel(
            tenant_id=tenant_id,
            secret_id=secret_id,
            version=version,
            ciphertext=ciphertext,
            nonce=nonce,
            dek_version=dek_version,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_version(row)

    async def get(
        self,
        secret_id: uuid.UUID,
        version: int,
        tenant_id: uuid.UUID,
    ) -> SecretVersion | None:
        row = await self._session.scalar(
            select(SecretVersionModel).where(
                SecretVersionModel.secret_id == secret_id,
                SecretVersionModel.version == version,
                SecretVersionModel.tenant_id == tenant_id,
            )
        )
        return _to_version(row) if row else None

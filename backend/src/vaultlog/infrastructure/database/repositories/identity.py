from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.identity.models import (
    AuthSession,
    RecoveryCode,
    RefreshToken,
    TotpSecret,
    User,
)
from vaultlog.infrastructure.database.identity_models import (
    AuthSessionModel,
    MembershipModel,
    RecoveryCodeModel,
    RefreshTokenModel,
    TotpSecretModel,
    UserModel,
)
from vaultlog.infrastructure.database.models import OrganizationModel


def _to_user(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        is_active=row.is_active,
        mfa_enabled=row.mfa_enabled,
    )


def _to_session(row: AuthSessionModel) -> AuthSession:
    return AuthSession(
        id=row.id,
        user_id=row.user_id,
        revoked_at=row.revoked_at,
        revocation_reason=row.revocation_reason,
        user_agent=row.user_agent,
        last_used_at=row.last_used_at,
    )


def _to_refresh_token(row: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        session_id=row.session_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
        revoked_at=row.revoked_at,
        replaced_by_id=row.replaced_by_id,
    )


def _to_totp_secret(row: TotpSecretModel) -> TotpSecret:
    return TotpSecret(
        id=row.id,
        user_id=row.user_id,
        encrypted_seed=row.encrypted_seed,
        seed_nonce=row.seed_nonce,
        confirmed=row.confirmed,
        confirmed_at=row.confirmed_at,
    )


def _to_recovery_code(row: RecoveryCodeModel) -> RecoveryCode:
    return RecoveryCode(
        id=row.id,
        user_id=row.user_id,
        code_hash=row.code_hash,
        used_at=row.used_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        return _to_user(row) if row is not None else None

    async def get(self, user_id: uuid.UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return _to_user(row) if row is not None else None

    async def add(self, email: str, password_hash: str) -> User:
        row = UserModel(email=email, password_hash=password_hash)
        self._session.add(row)
        await self._session.flush()
        return _to_user(row)

    async def set_mfa_enabled(self, user_id: uuid.UUID, enabled: bool) -> None:
        row = await self._session.get(UserModel, user_id)
        if row is None:
            return
        row.mfa_enabled = enabled


class SqlAlchemyMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        self._session.add(MembershipModel(tenant_id=tenant_id, user_id=user_id, role=role))
        await self._session.flush()

    async def get_default_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        result: uuid.UUID | None = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.user_id == user_id).limit(1)
        )
        return result


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: uuid.UUID, user_agent: str | None) -> AuthSession:
        row = AuthSessionModel(user_id=user_id, user_agent=user_agent)
        self._session.add(row)
        await self._session.flush()
        return _to_session(row)

    async def get(self, session_id: uuid.UUID) -> AuthSession | None:
        row = await self._session.get(AuthSessionModel, session_id)
        return _to_session(row) if row is not None else None

    async def revoke(
        self,
        session_id: uuid.UUID,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        row = await self._session.get(AuthSessionModel, session_id)
        if row is None:
            return
        row.revoked_at = revoked_at
        row.revocation_reason = reason

    async def touch(self, session_id: uuid.UUID, *, last_used_at: datetime) -> None:
        row = await self._session.get(AuthSessionModel, session_id)
        if row is None:
            return
        row.last_used_at = last_used_at


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        session_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        row = RefreshTokenModel(
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_refresh_token(row)

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        row = await self._session.scalar(
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        return _to_refresh_token(row) if row is not None else None

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        row = await self._session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        return _to_refresh_token(row) if row is not None else None

    async def mark_used(
        self,
        token_id: uuid.UUID,
        *,
        used_at: datetime,
        replaced_by_id: uuid.UUID,
    ) -> None:
        row = await self._session.get(RefreshTokenModel, token_id)
        if row is None:
            return
        row.used_at = used_at
        row.replaced_by_id = replaced_by_id


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, name: str) -> uuid.UUID:
        row = OrganizationModel(name=name)
        self._session.add(row)
        await self._session.flush()
        return row.id


class SqlAlchemyTotpSecretRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(TotpSecretModel).where(TotpSecretModel.user_id == user_id)
        )

    async def add(
        self,
        user_id: uuid.UUID,
        encrypted_seed: bytes,
        seed_nonce: bytes,
        *,
        confirmed: bool = False,
    ) -> TotpSecret:
        row = TotpSecretModel(
            user_id=user_id,
            encrypted_seed=encrypted_seed,
            seed_nonce=seed_nonce,
            confirmed=confirmed,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_totp_secret(row)

    async def get_unconfirmed(self, user_id: uuid.UUID) -> TotpSecret | None:
        row = await self._session.scalar(
            select(TotpSecretModel).where(
                TotpSecretModel.user_id == user_id,
                TotpSecretModel.confirmed.is_(False),
            )
        )
        return _to_totp_secret(row) if row is not None else None

    async def get_confirmed(self, user_id: uuid.UUID) -> TotpSecret | None:
        row = await self._session.scalar(
            select(TotpSecretModel).where(
                TotpSecretModel.user_id == user_id,
                TotpSecretModel.confirmed.is_(True),
            )
        )
        return _to_totp_secret(row) if row is not None else None

    async def confirm(self, user_id: uuid.UUID, confirmed_at: datetime) -> None:
        row = await self._session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == user_id)
        )
        if row is None:
            return
        row.confirmed = True
        row.confirmed_at = confirmed_at


class SqlAlchemyRecoveryCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(RecoveryCodeModel).where(RecoveryCodeModel.user_id == user_id)
        )

    async def add_batch(self, user_id: uuid.UUID, code_hashes: list[str]) -> None:
        for code_hash in code_hashes:
            self._session.add(RecoveryCodeModel(user_id=user_id, code_hash=code_hash))
        await self._session.flush()

    async def redeem_for_update(self, user_id: uuid.UUID, code_hash: str) -> bool:
        row = await self._session.scalar(
            select(RecoveryCodeModel)
            .where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.code_hash == code_hash,
                RecoveryCodeModel.used_at.is_(None),
            )
            .with_for_update()
        )
        if row is None:
            return False
        row.used_at = datetime.now(UTC)
        return True

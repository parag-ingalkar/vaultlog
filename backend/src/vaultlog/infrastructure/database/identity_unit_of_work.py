from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.domain.identity.ports import (
    MembershipRepository,
    OrganizationRepository,
    RecoveryCodeRepository,
    RefreshTokenRepository,
    SessionRepository,
    TotpSecretRepository,
    UserRepository,
)
from vaultlog.domain.organizations.ports import InvitationTokenLookup
from vaultlog.infrastructure.database.repositories.identity import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyRecoveryCodeRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyTotpSecretRepository,
    SqlAlchemyUserRepository,
)
from vaultlog.infrastructure.database.repositories.organizations import (
    SqlAlchemyInvitationTokenLookup,
)


class SqlAlchemyIdentityUnitOfWork:
    """Owner-role UoW for pre-tenant identity operations (no tenant GUC)."""

    users: UserRepository
    memberships: MembershipRepository
    sessions: SessionRepository
    refresh_tokens: RefreshTokenRepository
    organizations: OrganizationRepository
    totp_secrets: TotpSecretRepository
    recovery_codes: RecoveryCodeRepository
    invitation_lookup: InvitationTokenLookup

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session: AsyncSession = self._session_factory()
        await self.session.begin()
        self.users = SqlAlchemyUserRepository(self.session)
        self.memberships = SqlAlchemyMembershipRepository(self.session)
        self.sessions = SqlAlchemySessionRepository(self.session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(self.session)
        self.organizations = SqlAlchemyOrganizationRepository(self.session)
        self.totp_secrets = SqlAlchemyTotpSecretRepository(self.session)
        self.recovery_codes = SqlAlchemyRecoveryCodeRepository(self.session)
        self.invitation_lookup = SqlAlchemyInvitationTokenLookup(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

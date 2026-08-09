from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from vaultlog.application.ports.unit_of_work import UnitOfWork
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


class IdentityUnitOfWork(UnitOfWork, Protocol):
    users: UserRepository
    memberships: MembershipRepository
    sessions: SessionRepository
    refresh_tokens: RefreshTokenRepository
    organizations: OrganizationRepository
    totp_secrets: TotpSecretRepository
    recovery_codes: RecoveryCodeRepository
    invitation_lookup: InvitationTokenLookup

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

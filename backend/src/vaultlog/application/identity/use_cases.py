from __future__ import annotations

import uuid
from collections.abc import Callable

from vaultlog.application.ports.identity_unit_of_work import IdentityUnitOfWork
from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.domain.identity.models import TokenPair
from vaultlog.domain.identity.ports import PasswordHasher, TokenIssuer
from vaultlog.domain.identity.services import IdentityService


def _build_service(
    uow: IdentityUnitOfWork,
    passwords: PasswordHasher,
    tokens: TokenIssuer,
    refresh_ttl_days: int,
) -> IdentityService:
    return IdentityService(
        users=uow.users,
        memberships=uow.memberships,
        sessions=uow.sessions,
        refresh_tokens=uow.refresh_tokens,
        organizations=uow.organizations,
        passwords=passwords,
        tokens=tokens,
        refresh_ttl_days=refresh_ttl_days,
    )


class RegisterUser:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days

    async def execute(
        self,
        email: str,
        password: str,
        organization_name: str,
    ) -> uuid.UUID:
        async with self._uow_factory() as uow:
            service = _build_service(uow, self._passwords, self._tokens, self._refresh_ttl_days)
            user_id = await service.register(email, password, organization_name)
            await uow.commit()
            return user_id


class LoginUser:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days

    async def execute(
        self,
        email: str,
        password: str,
        user_agent: str | None,
    ) -> TokenPair:
        async with self._uow_factory() as uow:
            service = _build_service(uow, self._passwords, self._tokens, self._refresh_ttl_days)
            pair = await service.login(email, password, user_agent)
            await uow.commit()
            return pair


class RefreshTokens:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days

    async def execute(self, raw_refresh_token: str) -> TokenPair:
        auth_error: AuthenticationError | None = None
        async with self._uow_factory() as uow:
            service = _build_service(uow, self._passwords, self._tokens, self._refresh_ttl_days)
            try:
                pair = await service.refresh(raw_refresh_token)
            except AuthenticationError as exc:
                # Persist revocation side effects (reuse / expiry), then bubble
                # after the UoW exits so __aexit__ does not roll them back.
                await uow.commit()
                auth_error = exc
            else:
                await uow.commit()
                return pair
        assert auth_error is not None
        raise auth_error


class LogoutSession:
    def __init__(
        self,
        uow_factory: Callable[[], IdentityUnitOfWork],
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        refresh_ttl_days: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._passwords = passwords
        self._tokens = tokens
        self._refresh_ttl_days = refresh_ttl_days

    async def execute(self, raw_refresh_token: str) -> None:
        async with self._uow_factory() as uow:
            service = _build_service(uow, self._passwords, self._tokens, self._refresh_ttl_days)
            await service.logout(raw_refresh_token)
            await uow.commit()

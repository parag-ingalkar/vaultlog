from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    PasswordPolicyError,
    RegistrationConflictError,
)
from vaultlog.domain.identity.models import AuthSession, RefreshToken, User
from vaultlog.domain.identity.services import IdentityService
from vaultlog.infrastructure.security.passwords import Argon2Hasher


class FakePasswordHasher:
    def hash(self, plaintext: str) -> str:
        return f"hashed:{plaintext}"

    def verify(self, plaintext: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{plaintext}" or password_hash.startswith("$argon2id$")


class FakeTokenIssuer:
    def __init__(self) -> None:
        self._counter = 0

    def mint_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        amr: tuple[str, ...] = ("pwd",),
    ) -> str:
        return f"access:{user_id}:{tenant_id}:{session_id}:{','.join(amr)}"

    def verify_access_token(self, token: str):  # pragma: no cover - unused in these tests
        raise NotImplementedError

    def mint_challenge_token(self, user_id: uuid.UUID) -> str:
        return f"challenge:{user_id}"

    def verify_challenge_token(self, token: str) -> uuid.UUID:
        return uuid.UUID(token.split(":")[1])

    def mint_step_up_token(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> str:
        return f"step-up:{user_id}:{session_id}:{purpose}"

    def verify_step_up_token(
        self,
        token: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> None:
        expected = f"step-up:{user_id}:{session_id}:{purpose}"
        if token != expected:
            raise NotImplementedError

    def generate_refresh_token(self) -> str:
        self._counter += 1
        return f"refresh-raw-{self._counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        return f"hash:{raw_token}"


class InMemoryStore:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.users_by_email: dict[str, User] = {}
        self.memberships: dict[uuid.UUID, uuid.UUID] = {}  # user_id -> tenant_id
        self.sessions: dict[uuid.UUID, AuthSession] = {}
        self.refresh_tokens: dict[uuid.UUID, RefreshToken] = {}
        self.refresh_by_hash: dict[str, uuid.UUID] = {}
        self.organizations: dict[uuid.UUID, str] = {}


class FakeUserRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get_by_email(self, email: str) -> User | None:
        return self._store.users_by_email.get(email)

    async def get(self, user_id: uuid.UUID) -> User | None:
        return self._store.users.get(user_id)

    async def add(self, email: str, password_hash: str) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            mfa_enabled=False,
        )
        self._store.users[user.id] = user
        self._store.users_by_email[email] = user
        return user

    async def set_mfa_enabled(self, user_id: uuid.UUID, enabled: bool) -> None:
        user = self._store.users[user_id]
        self._store.users[user_id] = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            mfa_enabled=enabled,
        )
        self._store.users_by_email[user.email] = self._store.users[user_id]


class FakeMembershipRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def add(self, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        self._store.memberships[user_id] = tenant_id

    async def get_default_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return self._store.memberships.get(user_id)


class FakeSessionRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def add(self, user_id: uuid.UUID, user_agent: str | None) -> AuthSession:
        session = AuthSession(
            id=uuid.uuid4(),
            user_id=user_id,
            revoked_at=None,
            revocation_reason=None,
            user_agent=user_agent,
            last_used_at=datetime.now(UTC),
        )
        self._store.sessions[session.id] = session
        return session

    async def get(self, session_id: uuid.UUID) -> AuthSession | None:
        return self._store.sessions.get(session_id)

    async def revoke(
        self,
        session_id: uuid.UUID,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        session = self._store.sessions[session_id]
        self._store.sessions[session_id] = AuthSession(
            id=session.id,
            user_id=session.user_id,
            revoked_at=revoked_at,
            revocation_reason=reason,
            user_agent=session.user_agent,
            last_used_at=session.last_used_at,
        )

    async def touch(self, session_id: uuid.UUID, *, last_used_at: datetime) -> None:
        session = self._store.sessions[session_id]
        self._store.sessions[session_id] = AuthSession(
            id=session.id,
            user_id=session.user_id,
            revoked_at=session.revoked_at,
            revocation_reason=session.revocation_reason,
            user_agent=session.user_agent,
            last_used_at=last_used_at,
        )


class FakeRefreshTokenRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def add(
        self,
        session_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            id=uuid.uuid4(),
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
            revoked_at=None,
            replaced_by_id=None,
        )
        self._store.refresh_tokens[token.id] = token
        self._store.refresh_by_hash[token_hash] = token.id
        return token

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        return await self.get_by_hash(token_hash)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        token_id = self._store.refresh_by_hash.get(token_hash)
        if token_id is None:
            return None
        return self._store.refresh_tokens[token_id]

    async def mark_used(
        self,
        token_id: uuid.UUID,
        *,
        used_at: datetime,
        replaced_by_id: uuid.UUID,
    ) -> None:
        token = self._store.refresh_tokens[token_id]
        updated = RefreshToken(
            id=token.id,
            session_id=token.session_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            used_at=used_at,
            revoked_at=token.revoked_at,
            replaced_by_id=replaced_by_id,
        )
        self._store.refresh_tokens[token_id] = updated


class FakeOrganizationRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def add(self, name: str) -> uuid.UUID:
        org_id = uuid.uuid4()
        self._store.organizations[org_id] = name
        return org_id


def build_service(store: InMemoryStore | None = None) -> tuple[IdentityService, InMemoryStore]:
    store = store or InMemoryStore()
    service = IdentityService(
        users=FakeUserRepository(store),
        memberships=FakeMembershipRepository(store),
        sessions=FakeSessionRepository(store),
        refresh_tokens=FakeRefreshTokenRepository(store),
        organizations=FakeOrganizationRepository(store),
        passwords=FakePasswordHasher(),
        tokens=FakeTokenIssuer(),
        refresh_ttl_days=30,
    )
    return service, store


@pytest.mark.asyncio
async def test_register_creates_user_org_and_membership() -> None:
    service, store = build_service()
    user_id, _tenant_id = await service.register("Ada@Example.com", "correct horse battery", "Acme")
    user = store.users[user_id]
    assert user.email == "ada@example.com"
    assert store.memberships[user_id] in store.organizations


@pytest.mark.asyncio
async def test_register_rejects_weak_password() -> None:
    service, _ = build_service()
    with pytest.raises(PasswordPolicyError):
        await service.register("ada@example.com", "short", "Acme")


@pytest.mark.asyncio
async def test_register_conflict_on_duplicate_email() -> None:
    service, _ = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    with pytest.raises(RegistrationConflictError):
        await service.register("ada@example.com", "correct horse battery", "Other")


@pytest.mark.asyncio
async def test_login_returns_token_pair() -> None:
    service, _ = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    result = await service.login("ada@example.com", "correct horse battery", "pytest")
    assert result.kind == "tokens"
    assert result.pair is not None
    assert result.pair.access_token.startswith("access:")
    assert result.pair.refresh_token.startswith("refresh-raw-")


@pytest.mark.asyncio
async def test_wrong_password_and_unknown_email_same_error() -> None:
    service, _ = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await service.login("ada@example.com", "wrong password!!", None)
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await service.login("nobody@example.com", "any password 12", None)


@pytest.mark.asyncio
async def test_refresh_rotation_consumes_old_token() -> None:
    service, store = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    login_result = await service.login("ada@example.com", "correct horse battery", "pytest")
    pair1 = login_result.pair
    assert pair1 is not None
    pair2 = await service.refresh(pair1.refresh_token)
    assert pair2.refresh_token != pair1.refresh_token

    old_hash = FakeTokenIssuer().hash_refresh_token(pair1.refresh_token)
    old_id = store.refresh_by_hash[old_hash]
    assert store.refresh_tokens[old_id].used_at is not None

    with pytest.raises(AuthenticationError):
        await service.refresh(pair1.refresh_token)


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_session_family() -> None:
    service, store = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    login_result = await service.login("ada@example.com", "correct horse battery", "pytest")
    pair1 = login_result.pair
    assert pair1 is not None
    pair2 = await service.refresh(pair1.refresh_token)

    with pytest.raises(AuthenticationError):
        await service.refresh(pair1.refresh_token)

    session = next(iter(store.sessions.values()))
    assert session.revoked_at is not None
    assert session.revocation_reason == "refresh_reuse_detected"

    with pytest.raises(AuthenticationError):
        await service.refresh(pair2.refresh_token)


@pytest.mark.asyncio
async def test_logout_revokes_session() -> None:
    service, store = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    login_result = await service.login("ada@example.com", "correct horse battery", "pytest")
    pair = login_result.pair
    assert pair is not None
    await service.logout(pair.refresh_token)
    session = next(iter(store.sessions.values()))
    assert session.revocation_reason == "user_logout"
    with pytest.raises(AuthenticationError):
        await service.refresh(pair.refresh_token)


@pytest.mark.asyncio
async def test_expired_refresh_revokes_session() -> None:
    service, store = build_service()
    await service.register("ada@example.com", "correct horse battery", "Acme")
    login_result = await service.login("ada@example.com", "correct horse battery", "pytest")
    pair = login_result.pair
    assert pair is not None
    token_hash = FakeTokenIssuer().hash_refresh_token(pair.refresh_token)
    token_id = store.refresh_by_hash[token_hash]
    token = store.refresh_tokens[token_id]
    store.refresh_tokens[token_id] = RefreshToken(
        id=token.id,
        session_id=token.session_id,
        token_hash=token.token_hash,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        used_at=None,
        revoked_at=None,
        replaced_by_id=None,
    )
    with pytest.raises(AuthenticationError):
        await service.refresh(pair.refresh_token)
    session = store.sessions[token.session_id]
    assert session.revocation_reason == "refresh_expired"


@pytest.mark.asyncio
async def test_real_argon2_hasher_round_trip() -> None:
    hasher = Argon2Hasher()
    digest = hasher.hash("correct horse battery")
    assert hasher.verify("correct horse battery", digest)
    assert not hasher.verify("wrong password!!", digest)

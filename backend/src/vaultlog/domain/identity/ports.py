from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from vaultlog.domain.identity.models import (
    AccessTokenClaims,
    AuthSession,
    RefreshToken,
    TotpSecret,
    User,
)


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def add(self, email: str, password_hash: str) -> User: ...

    async def set_mfa_enabled(self, user_id: uuid.UUID, enabled: bool) -> None: ...


class MembershipRepository(Protocol):
    async def add(self, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None: ...

    async def get_default_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID | None: ...


class SessionRepository(Protocol):
    async def add(self, user_id: uuid.UUID, user_agent: str | None) -> AuthSession: ...

    async def get(self, session_id: uuid.UUID) -> AuthSession | None: ...

    async def revoke(
        self,
        session_id: uuid.UUID,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...

    async def touch(self, session_id: uuid.UUID, *, last_used_at: datetime) -> None: ...


class RefreshTokenRepository(Protocol):
    async def add(
        self,
        session_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken: ...

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def mark_used(
        self,
        token_id: uuid.UUID,
        *,
        used_at: datetime,
        replaced_by_id: uuid.UUID,
    ) -> None: ...


class TotpSecretRepository(Protocol):
    async def delete_for_user(self, user_id: uuid.UUID) -> None: ...

    async def add(
        self,
        user_id: uuid.UUID,
        encrypted_seed: bytes,
        seed_nonce: bytes,
        *,
        confirmed: bool = False,
    ) -> TotpSecret: ...

    async def get_unconfirmed(self, user_id: uuid.UUID) -> TotpSecret | None: ...

    async def get_confirmed(self, user_id: uuid.UUID) -> TotpSecret | None: ...

    async def confirm(self, user_id: uuid.UUID, confirmed_at: datetime) -> None: ...


class RecoveryCodeRepository(Protocol):
    async def delete_for_user(self, user_id: uuid.UUID) -> None: ...

    async def add_batch(self, user_id: uuid.UUID, code_hashes: list[str]) -> None: ...

    async def redeem_for_update(self, user_id: uuid.UUID, code_hash: str) -> bool: ...


class OrganizationRepository(Protocol):
    async def add(self, name: str) -> uuid.UUID: ...


class RateLimitGate(Protocol):
    async def check(
        self,
        key: str,
        *,
        capacity: int,
        window_seconds: int,
        fail_closed: bool = False,
    ) -> bool: ...


class PasswordHasher(Protocol):
    def hash(self, plaintext: str) -> str: ...

    def verify(self, plaintext: str, password_hash: str) -> bool: ...


class SeedEncryptor(Protocol):
    def encrypt(self, user_id: uuid.UUID, seed: str) -> tuple[bytes, bytes]: ...

    def decrypt(self, user_id: uuid.UUID, nonce: bytes, ciphertext: bytes) -> str: ...


class TotpVerifier(Protocol):
    def generate_seed(self) -> str: ...

    def provisioning_uri(self, seed: str, email: str) -> str: ...

    def verify_totp(self, seed: str, code: str) -> bool: ...

    def generate_recovery_codes(self, count: int = 10) -> list[str]: ...

    def hash_recovery_code(self, code: str) -> str: ...


class TokenIssuer(Protocol):
    def mint_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        amr: tuple[str, ...] = ("pwd",),
    ) -> str: ...

    def verify_access_token(self, token: str) -> AccessTokenClaims: ...

    def mint_challenge_token(self, user_id: uuid.UUID) -> str: ...

    def verify_challenge_token(self, token: str) -> uuid.UUID: ...

    def mint_step_up_token(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> str: ...

    def verify_step_up_token(
        self,
        token: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> None: ...

    def generate_refresh_token(self) -> str: ...

    def hash_refresh_token(self, raw_token: str) -> str: ...

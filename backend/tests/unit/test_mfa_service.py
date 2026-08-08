from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pyotp
import pytest
from tests.unit.test_identity_service import (
    FakeMembershipRepository,
    FakeRefreshTokenRepository,
    FakeSessionRepository,
    FakeTokenIssuer,
    FakeUserRepository,
    InMemoryStore,
)

from vaultlog.domain.identity.exceptions import (
    MfaEnrollmentError,
    MfaVerificationError,
)
from vaultlog.domain.identity.models import RecoveryCode, TotpSecret, User
from vaultlog.domain.identity.services import MfaService
from vaultlog.infrastructure.security.mfa import PyotpTotpVerifier
from vaultlog.infrastructure.security.seed_encryption import AesGcmSeedEncryptor
from vaultlog.shared.config import get_settings


class FakeTotpSecretRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        self._store.totp_secrets.pop(user_id, None)

    async def add(
        self,
        user_id: uuid.UUID,
        encrypted_seed: bytes,
        seed_nonce: bytes,
        *,
        confirmed: bool = False,
    ) -> TotpSecret:
        secret = TotpSecret(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_seed=encrypted_seed,
            seed_nonce=seed_nonce,
            confirmed=confirmed,
            confirmed_at=None,
        )
        self._store.totp_secrets[user_id] = secret
        return secret

    async def get_unconfirmed(self, user_id: uuid.UUID) -> TotpSecret | None:
        secret = self._store.totp_secrets.get(user_id)
        if secret is None or secret.confirmed:
            return None
        return secret

    async def get_confirmed(self, user_id: uuid.UUID) -> TotpSecret | None:
        secret = self._store.totp_secrets.get(user_id)
        if secret is None or not secret.confirmed:
            return None
        return secret

    async def confirm(self, user_id: uuid.UUID, confirmed_at: datetime) -> None:
        secret = self._store.totp_secrets.get(user_id)
        if secret is None:
            return
        self._store.totp_secrets[user_id] = TotpSecret(
            id=secret.id,
            user_id=secret.user_id,
            encrypted_seed=secret.encrypted_seed,
            seed_nonce=secret.seed_nonce,
            confirmed=True,
            confirmed_at=confirmed_at,
        )


class FakeRecoveryCodeRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        self._store.recovery_codes.pop(user_id, None)

    async def add_batch(self, user_id: uuid.UUID, code_hashes: list[str]) -> None:
        codes = [
            RecoveryCode(id=uuid.uuid4(), user_id=user_id, code_hash=h, used_at=None)
            for h in code_hashes
        ]
        self._store.recovery_codes[user_id] = codes

    async def redeem_for_update(self, user_id: uuid.UUID, code_hash: str) -> bool:
        codes = self._store.recovery_codes.get(user_id, [])
        for i, code in enumerate(codes):
            if code.code_hash == code_hash and code.used_at is None:
                codes[i] = RecoveryCode(
                    id=code.id,
                    user_id=code.user_id,
                    code_hash=code.code_hash,
                    used_at=datetime.now(UTC),
                )
                return True
        return False


def build_mfa_service(store: InMemoryStore | None = None) -> tuple[MfaService, InMemoryStore, str]:
    store = store or InMemoryStore()
    if not hasattr(store, "totp_secrets"):
        store.totp_secrets = {}
    if not hasattr(store, "recovery_codes"):
        store.recovery_codes = {}

    encryptor = AesGcmSeedEncryptor(get_settings())
    verifier = PyotpTotpVerifier()
    tokens = FakeTokenIssuer()

    service = MfaService(
        users=FakeUserRepository(store),
        memberships=FakeMembershipRepository(store),
        sessions=FakeSessionRepository(store),
        refresh_tokens=FakeRefreshTokenRepository(store),
        totp_secrets=FakeTotpSecretRepository(store),
        recovery_codes=FakeRecoveryCodeRepository(store),
        seed_encryptor=encryptor,
        totp_verifier=verifier,
        tokens=tokens,
        refresh_ttl_days=30,
    )
    return service, store, verifier.generate_seed()


@pytest.mark.asyncio
async def test_two_phase_enrollment() -> None:
    service, store, _ = build_mfa_service()
    user_id = uuid.uuid4()
    store.users[user_id] = User(
        id=user_id,
        email="ada@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=False,
    )
    store.memberships[user_id] = uuid.uuid4()

    result = await service.start_enrollment(user_id, "ada@example.com")
    assert result.provisioning_uri.startswith("otpauth://")

    secret = store.totp_secrets[user_id]
    seed = AesGcmSeedEncryptor(get_settings()).decrypt(
        user_id, secret.seed_nonce, secret.encrypted_seed
    )
    code = pyotp.TOTP(seed).now()
    codes = await service.confirm_enrollment(user_id, code)
    assert len(codes) == 10
    assert store.users[user_id].mfa_enabled


@pytest.mark.asyncio
async def test_confirm_enrollment_rejects_wrong_code() -> None:
    service, store, _ = build_mfa_service()
    user_id = uuid.uuid4()
    store.users[user_id] = User(
        id=user_id,
        email="ada@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=False,
    )
    await service.start_enrollment(user_id, "ada@example.com")
    with pytest.raises(MfaEnrollmentError):
        await service.confirm_enrollment(user_id, "000000")


@pytest.mark.asyncio
async def test_complete_login_issues_totp_amr() -> None:
    service, store, seed = build_mfa_service()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    store.users[user_id] = User(
        id=user_id,
        email="ada@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=True,
    )
    store.memberships[user_id] = tenant_id

    nonce, ciphertext = AesGcmSeedEncryptor(get_settings()).encrypt(user_id, seed)
    store.totp_secrets[user_id] = TotpSecret(
        id=uuid.uuid4(),
        user_id=user_id,
        encrypted_seed=ciphertext,
        seed_nonce=nonce,
        confirmed=True,
        confirmed_at=datetime.now(UTC),
    )

    challenge = FakeTokenIssuer().mint_challenge_token(user_id)
    code = pyotp.TOTP(seed).now()
    pair = await service.complete_login(challenge, code, "pytest")
    assert "pwd,totp" in pair.access_token


@pytest.mark.asyncio
async def test_recovery_code_single_use() -> None:
    service, store, seed = build_mfa_service()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    store.users[user_id] = User(
        id=user_id,
        email="ada@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=True,
    )
    store.memberships[user_id] = tenant_id

    nonce, ciphertext = AesGcmSeedEncryptor(get_settings()).encrypt(user_id, seed)
    store.totp_secrets[user_id] = TotpSecret(
        id=uuid.uuid4(),
        user_id=user_id,
        encrypted_seed=ciphertext,
        seed_nonce=nonce,
        confirmed=True,
        confirmed_at=datetime.now(UTC),
    )

    verifier = PyotpTotpVerifier()
    raw_code = verifier.generate_recovery_codes()[0]
    store.recovery_codes[user_id] = [
        RecoveryCode(
            id=uuid.uuid4(),
            user_id=user_id,
            code_hash=verifier.hash_recovery_code(raw_code),
            used_at=None,
        )
    ]

    challenge = FakeTokenIssuer().mint_challenge_token(user_id)
    await service.complete_login(challenge, raw_code, "pytest")
    with pytest.raises(MfaVerificationError):
        await service.complete_login(challenge, raw_code, "pytest")


@pytest.mark.asyncio
async def test_challenge_token_not_step_up() -> None:
    tokens = FakeTokenIssuer()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    challenge = tokens.mint_challenge_token(user_id)
    with pytest.raises(NotImplementedError):
        tokens.verify_step_up_token(
            challenge,
            user_id,
            session_id,
            "step-up:manage-mfa",
        )


@pytest.mark.asyncio
async def test_disable_mfa_clears_data() -> None:
    service, store, seed = build_mfa_service()
    user_id = uuid.uuid4()
    store.users[user_id] = User(
        id=user_id,
        email="ada@example.com",
        password_hash="hash",
        is_active=True,
        mfa_enabled=True,
    )
    nonce, ciphertext = AesGcmSeedEncryptor(get_settings()).encrypt(user_id, seed)
    store.totp_secrets[user_id] = TotpSecret(
        id=uuid.uuid4(),
        user_id=user_id,
        encrypted_seed=ciphertext,
        seed_nonce=nonce,
        confirmed=True,
        confirmed_at=datetime.now(UTC),
    )
    store.recovery_codes[user_id] = [
        RecoveryCode(id=uuid.uuid4(), user_id=user_id, code_hash="abc", used_at=None)
    ]

    await service.disable_mfa(user_id)
    assert user_id not in store.totp_secrets
    assert user_id not in store.recovery_codes
    assert not store.users[user_id].mfa_enabled

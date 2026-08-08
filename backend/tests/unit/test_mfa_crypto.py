from __future__ import annotations

import uuid

import pyotp
import pytest

from vaultlog.infrastructure.security.mfa import PyotpTotpVerifier
from vaultlog.infrastructure.security.seed_encryption import (
    AesGcmSeedEncryptor,
    SeedDecryptionError,
)
from vaultlog.shared.config import get_settings


def test_totp_verify_accepts_current_code() -> None:
    verifier = PyotpTotpVerifier()
    seed = verifier.generate_seed()
    code = pyotp.TOTP(seed).now()
    assert verifier.verify_totp(seed, code)


def test_totp_verify_rejects_wrong_code() -> None:
    verifier = PyotpTotpVerifier()
    seed = verifier.generate_seed()
    assert not verifier.verify_totp(seed, "000000")


def test_seed_encryption_round_trip() -> None:
    encryptor = AesGcmSeedEncryptor(get_settings())
    uid = uuid.uuid4()
    nonce, ciphertext = encryptor.encrypt(uid, "JBSWY3DPEHPK3PXP")
    assert encryptor.decrypt(uid, nonce, ciphertext) == "JBSWY3DPEHPK3PXP"


def test_seed_ciphertext_bound_to_user() -> None:
    encryptor = AesGcmSeedEncryptor(get_settings())
    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    nonce, ciphertext = encryptor.encrypt(uid_a, "JBSWY3DPEHPK3PXP")
    with pytest.raises(SeedDecryptionError):
        encryptor.decrypt(uid_b, nonce, ciphertext)


def test_recovery_code_hash_normalizes_input() -> None:
    verifier = PyotpTotpVerifier()
    code = "ABCDE-23456"
    assert verifier.hash_recovery_code(code) == verifier.hash_recovery_code("abcde23456")


def test_recovery_codes_are_unique_and_unambiguous() -> None:
    verifier = PyotpTotpVerifier()
    codes = verifier.generate_recovery_codes()
    assert len(set(codes)) == 10
    for code in codes:
        assert "0" not in code and "O" not in code and "1" not in code and "I" not in code

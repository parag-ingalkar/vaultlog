from __future__ import annotations

import uuid

import pytest

from vaultlog.domain.secrets.aad import dek_wrap_aad, secret_aad
from vaultlog.domain.secrets.exceptions import CryptoError
from vaultlog.infrastructure.security.vault_crypto import (
    AesGcmSecretEncryptor,
    LocalKEKProvider,
)
from vaultlog.shared.config import get_settings

T = uuid.uuid4()
V = uuid.uuid4()
S = uuid.uuid4()


def test_round_trip() -> None:
    encryptor = AesGcmSecretEncryptor()
    dek = encryptor.generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encryptor.encrypt_secret(dek, b"hunter2", aad)
    assert encryptor.decrypt_secret(dek, nonce, ct, aad) == b"hunter2"
    assert b"hunter2" not in ct


def test_tampered_ciphertext_fails() -> None:
    encryptor = AesGcmSecretEncryptor()
    dek = encryptor.generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encryptor.encrypt_secret(dek, b"hunter2", aad)
    tampered = bytes([ct[0] ^ 1]) + ct[1:]
    with pytest.raises(CryptoError):
        encryptor.decrypt_secret(dek, nonce, tampered, aad)


def test_wrong_aad_fails() -> None:
    encryptor = AesGcmSecretEncryptor()
    dek = encryptor.generate_dek()
    nonce, ct = encryptor.encrypt_secret(dek, b"hunter2", secret_aad(T, V, S, 1))
    with pytest.raises(CryptoError):
        encryptor.decrypt_secret(dek, nonce, ct, secret_aad(T, V, S, 2))
    with pytest.raises(CryptoError):
        encryptor.decrypt_secret(
            dek,
            nonce,
            ct,
            secret_aad(uuid.uuid4(), V, S, 1),
        )


def test_wrong_dek_fails() -> None:
    encryptor = AesGcmSecretEncryptor()
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encryptor.encrypt_secret(encryptor.generate_dek(), b"x", aad)
    with pytest.raises(CryptoError):
        encryptor.decrypt_secret(encryptor.generate_dek(), nonce, ct, aad)


def test_nonces_are_unique() -> None:
    encryptor = AesGcmSecretEncryptor()
    dek = encryptor.generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonces = {encryptor.encrypt_secret(dek, b"same", aad)[0] for _ in range(1000)}
    assert len(nonces) == 1000


def test_kek_wrap_unwrap_and_aad_binding() -> None:
    kek = LocalKEKProvider(get_settings())
    encryptor = AesGcmSecretEncryptor()
    dek = encryptor.generate_dek()
    nonce, wrapped, key_id = kek.wrap(dek, dek_wrap_aad(T, 1))
    assert dek not in wrapped
    assert kek.unwrap(nonce, wrapped, dek_wrap_aad(T, 1), key_id) == dek
    with pytest.raises(CryptoError):
        kek.unwrap(nonce, wrapped, dek_wrap_aad(uuid.uuid4(), 1), key_id)
    with pytest.raises(CryptoError):
        kek.unwrap(nonce, wrapped, dek_wrap_aad(T, 1), "some-other-key")

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultlog.domain.secrets.exceptions import CryptoError
from vaultlog.domain.secrets.ports import KEKProvider, SecretEncryptor
from vaultlog.shared.config import Settings

DEK_SIZE = 32
GCM_NONCE_SIZE = 12


class AesGcmSecretEncryptor(SecretEncryptor):
    def generate_dek(self) -> bytes:
        return os.urandom(DEK_SIZE)

    def encrypt_secret(
        self,
        dek: bytes,
        plaintext: bytes,
        aad: bytes,
    ) -> tuple[bytes, bytes]:
        if len(dek) != DEK_SIZE:
            raise CryptoError("Invalid DEK size")
        nonce = os.urandom(GCM_NONCE_SIZE)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
        return nonce, ciphertext

    def decrypt_secret(
        self,
        dek: bytes,
        nonce: bytes,
        ciphertext: bytes,
        aad: bytes,
    ) -> bytes:
        try:
            return AESGCM(dek).decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise CryptoError("Decryption failed") from exc


class LocalKEKProvider(KEKProvider):
    KEY_ID = "local-kek-v1"

    def __init__(self, settings: Settings) -> None:
        kek = base64.b64decode(settings.master_key_b64)
        if len(kek) != DEK_SIZE:
            raise CryptoError("MASTER_KEY_B64 must decode to 32 bytes")
        self._kek = kek

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]:
        nonce = os.urandom(GCM_NONCE_SIZE)
        wrapped = AESGCM(self._kek).encrypt(nonce, dek, aad)
        return nonce, wrapped, self.KEY_ID

    def unwrap(
        self,
        nonce: bytes,
        wrapped_dek: bytes,
        aad: bytes,
        wrapping_key_id: str,
    ) -> bytes:
        if wrapping_key_id != self.KEY_ID:
            raise CryptoError("Unknown wrapping key")
        try:
            return AESGCM(self._kek).decrypt(nonce, wrapped_dek, aad)
        except Exception as exc:
            raise CryptoError("DEK unwrap failed") from exc

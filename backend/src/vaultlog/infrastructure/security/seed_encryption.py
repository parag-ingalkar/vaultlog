from __future__ import annotations

import base64
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultlog.shared.config import Settings


class SeedDecryptionError(Exception):
    pass


class AesGcmSeedEncryptor:
    def __init__(self, settings: Settings) -> None:
        key = base64.b64decode(settings.mfa_kek_b64)
        if len(key) != 32:
            raise ValueError("MFA_KEK_B64 must decode to exactly 32 bytes")
        self._kek = key

    def encrypt(self, user_id: UUID, seed: str) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        aad = f"vaultlog:totp-seed:v1:{user_id}".encode()
        ciphertext = AESGCM(self._kek).encrypt(nonce, seed.encode(), aad)
        return nonce, ciphertext

    def decrypt(self, user_id: UUID, nonce: bytes, ciphertext: bytes) -> str:
        aad = f"vaultlog:totp-seed:v1:{user_id}".encode()
        try:
            return AESGCM(self._kek).decrypt(nonce, ciphertext, aad).decode()
        except Exception as exc:
            raise SeedDecryptionError("TOTP seed could not be decrypted") from exc

from __future__ import annotations

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = Argon2PasswordHasher()


class Argon2Hasher:
    def hash(self, plaintext: str) -> str:
        return _hasher.hash(plaintext)

    def verify(self, plaintext: str, password_hash: str) -> bool:
        try:
            return _hasher.verify(password_hash, plaintext)
        except (VerifyMismatchError, VerificationError):
            return False

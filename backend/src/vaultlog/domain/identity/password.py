from __future__ import annotations

from vaultlog.domain.identity.exceptions import PasswordPolicyError


def validate_password_strength(plaintext: str) -> None:
    if not 12 <= len(plaintext) <= 128:
        raise PasswordPolicyError("Password must be between 12 and 128 characters")

from __future__ import annotations

import hashlib
import secrets

import pyotp


class PyotpTotpVerifier:
    def generate_seed(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, seed: str, email: str) -> str:
        return pyotp.TOTP(seed).provisioning_uri(name=email, issuer_name="VaultLog")

    def verify_totp(self, seed: str, code: str) -> bool:
        return pyotp.TOTP(seed).verify(code.strip(), valid_window=1)

    def generate_recovery_codes(self, count: int = 10) -> list[str]:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(count)]

    def hash_recovery_code(self, code: str) -> str:
        normalized = code.strip().upper().replace("-", "").replace(" ", "")
        return hashlib.sha256(normalized.encode()).hexdigest()

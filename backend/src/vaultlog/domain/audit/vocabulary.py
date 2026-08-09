from __future__ import annotations

AUDIT_ACTIONS = frozenset(
    {
        "vault.created",
        "vault.deleted",
        "vault.updated",
        "grant.created",
        "grant.updated",
        "grant.revoked",
        "secret.created",
        "secret.revealed",
        "secret.rotated",
        "secret.deleted",
        "key.rotated",
        "member.invited",
        "member.removed",
        "member.role_changed",
        "mfa.enabled",
        "mfa.disabled",
        "stepup.issued",
        "access.denied",
    }
)

FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "value",
        "plaintext",
        "password",
        "secret",
        "token",
        "code",
        "refresh_token",
        "access_token",
        "totp",
        "seed",
        "key",
        "dek",
    }
)

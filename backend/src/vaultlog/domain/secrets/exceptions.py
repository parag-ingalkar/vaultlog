class CryptoError(Exception):
    """Opaque crypto failure — never expose padding, tag, or key details."""


class NoActiveKeyError(Exception):
    pass


class SecretConflictError(Exception):
    pass


class TenantKeyProvisionError(Exception):
    """Tenant encryption key could not be provisioned after registration."""

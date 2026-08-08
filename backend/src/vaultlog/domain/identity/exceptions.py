from __future__ import annotations


class DomainError(Exception):
    """Base for identity domain errors — mapped to HTTP by presentation handlers."""


class PasswordPolicyError(DomainError):
    pass


class RegistrationConflictError(DomainError):
    """Raised when registration cannot proceed. Message must stay generic."""


class AuthenticationError(DomainError):
    """Opaque auth failure for login, refresh, and related flows."""


class TokenValidationError(DomainError):
    """Raised when an access token fails verification."""


class MfaEnrollmentError(DomainError):
    """Raised when MFA enrollment cannot proceed or confirmation fails."""


class MfaVerificationError(DomainError):
    """Raised when MFA verification fails during login challenge."""


class StepUpRequiredError(DomainError):
    """Raised when a sensitive operation lacks valid step-up proof."""

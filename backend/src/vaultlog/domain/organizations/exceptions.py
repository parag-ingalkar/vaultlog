from __future__ import annotations

from vaultlog.domain.identity.exceptions import DomainError


class InvitationError(DomainError):
    """Raised when an invitation cannot be created or accepted."""


class InvitationNotFoundError(DomainError):
    """Raised when an invitation does not exist or is no longer valid."""


class MemberConflictError(DomainError):
    """Raised when a membership operation conflicts with existing state."""


class MemberNotFoundError(DomainError):
    """Raised when a membership cannot be found."""

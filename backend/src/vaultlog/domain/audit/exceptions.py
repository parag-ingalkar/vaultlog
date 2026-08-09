from __future__ import annotations


class AuditError(Exception):
    """Base for audit domain errors."""


class AuditMetadataError(AuditError, ValueError):
    """Raised when audit metadata contains forbidden keys."""


class UnknownAuditActionError(AuditError, ValueError):
    """Raised when an action is not in the closed vocabulary."""

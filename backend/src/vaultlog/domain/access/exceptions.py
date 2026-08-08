from __future__ import annotations


class AccessError(Exception):
    """Base for authorization domain errors."""


class ForbiddenError(AccessError):
    """Raised for every denial. Mapped to 403 — never leak why."""


class NotFoundError(AccessError):
    """Resource absent or invisible. Indistinguishable from the caller's view."""

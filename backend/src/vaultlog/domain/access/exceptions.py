from __future__ import annotations

import uuid


class AccessError(Exception):
    """Base for authorization domain errors."""


class ForbiddenError(AccessError):
    """Raised for every denial. Mapped to 403 — never leak why."""

    def __init__(
        self,
        message: str = "Access denied",
        *,
        audit_denial: bool = False,
        attempted_action: str | None = None,
        audit_target_type: str | None = None,
        audit_target_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.audit_denial = audit_denial
        self.attempted_action = attempted_action
        self.audit_target_type = audit_target_type
        self.audit_target_id = audit_target_id


class NotFoundError(AccessError):
    """Resource absent or invisible. Indistinguishable from the caller's view."""

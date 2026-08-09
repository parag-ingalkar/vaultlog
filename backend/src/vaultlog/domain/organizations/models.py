from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from vaultlog.domain.access.models import OrgRole


@dataclass(frozen=True)
class Invitation:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: OrgRole
    token_hash: str
    invited_by_user_id: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class InvitationPreview:
    organization_name: str
    role: OrgRole
    email_masked: str


@dataclass(frozen=True)
class MemberView:
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: OrgRole
    created_at: datetime


@dataclass(frozen=True)
class OrganizationView:
    id: uuid.UUID
    name: str
    caller_role: OrgRole

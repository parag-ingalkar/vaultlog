from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class VaultPermission(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return {"read": 1, "write": 2, "admin": 3}[self.value]


class Action(StrEnum):
    VAULT_LIST = "vault.list"
    VAULT_CREATE = "vault.create"
    VAULT_UPDATE = "vault.update"
    VAULT_DELETE = "vault.delete"
    GRANT_MANAGE = "grant.manage"
    SECRET_READ_META = "secret.read_meta"
    SECRET_REVEAL = "secret.reveal"
    SECRET_WRITE = "secret.write"
    SECRET_DELETE = "secret.delete"
    MEMBER_INVITE = "member.invite"
    MEMBER_REMOVE = "member.remove"
    AUDIT_READ = "audit.read"


@dataclass(frozen=True)
class AccessContext:
    user_id: UUID
    tenant_id: UUID
    role: OrgRole
    vault_permission: VaultPermission | None

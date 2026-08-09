from __future__ import annotations

import uuid

from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import (
    AccessContext,
    Action,
    OrgRole,
    VaultPermission,
)
from vaultlog.domain.access.ports import (
    MembershipAccessPort,
    VaultAccessPort,
    VaultGrantAccessPort,
)

_SENSITIVE_VAULT_ACTIONS = frozenset(
    {
        Action.SECRET_REVEAL,
        Action.SECRET_WRITE,
        Action.SECRET_DELETE,
        Action.VAULT_DELETE,
        Action.GRANT_MANAGE,
    }
)

_ACTION_TO_ATTEMPTED_AUDIT: dict[Action, str] = {
    Action.SECRET_REVEAL: "secret.revealed",
    Action.SECRET_DELETE: "secret.deleted",
    Action.SECRET_WRITE: "secret.created",
    Action.VAULT_DELETE: "vault.deleted",
    Action.GRANT_MANAGE: "grant.created",
}


def _forbidden_vault_action(action: Action, vault_id: uuid.UUID) -> ForbiddenError:
    if action in _SENSITIVE_VAULT_ACTIONS:
        return ForbiddenError(
            "Access denied",
            audit_denial=True,
            attempted_action=_ACTION_TO_ATTEMPTED_AUDIT.get(action, action.value),
            audit_target_type="vault",
            audit_target_id=vault_id,
        )
    return ForbiddenError("Access denied")


def _org_allows(role: OrgRole, action: Action) -> bool:
    """Baseline org-role permissions, independent of vault grants."""
    match action:
        case Action.VAULT_LIST | Action.SECRET_READ_META:
            return True
        case Action.VAULT_CREATE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case Action.VAULT_UPDATE | Action.VAULT_DELETE | Action.GRANT_MANAGE | Action.MEMBER_INVITE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case Action.MEMBER_REMOVE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case Action.SECRET_WRITE | Action.SECRET_DELETE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MEMBER)
        case Action.AUDIT_READ:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case _:
            return False


def _member_allows(action: Action) -> bool:
    return action in (
        Action.SECRET_READ_META,
        Action.SECRET_REVEAL,
        Action.SECRET_WRITE,
        Action.SECRET_DELETE,
    )


def _viewer_allows(action: Action) -> bool:
    return action in (Action.SECRET_READ_META, Action.SECRET_REVEAL)


def _grant_allows(
    permission: VaultPermission | None,
    action: Action,
    *,
    role: OrgRole,
) -> bool:
    if permission is None:
        return False

    if role is OrgRole.VIEWER and action not in (
        Action.SECRET_READ_META,
        Action.SECRET_REVEAL,
    ):
        return False

    match action:
        case Action.SECRET_READ_META | Action.SECRET_REVEAL:
            return permission.rank >= VaultPermission.READ.rank
        case Action.SECRET_WRITE:
            return permission.rank >= VaultPermission.WRITE.rank
        case Action.SECRET_DELETE:
            return permission.rank >= VaultPermission.ADMIN.rank
        case _:
            return False


class PolicyService:
    """Single entry point for every authorization decision."""

    def __init__(
        self,
        memberships: MembershipAccessPort,
        vaults: VaultAccessPort,
        grants: VaultGrantAccessPort,
    ) -> None:
        self._memberships = memberships
        self._vaults = vaults
        self._grants = grants

    async def require_org(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        action: Action,
    ) -> AccessContext:
        role = await self._memberships.get_role(user_id, tenant_id)
        if role is None or not _org_allows(role, action):
            raise ForbiddenError("Access denied")
        return AccessContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            vault_permission=None,
        )

    async def require_vault(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        vault_id: uuid.UUID,
        action: Action,
    ) -> AccessContext:
        if not await self._vaults.exists_active(vault_id, tenant_id):
            raise NotFoundError("Vault not found")

        role = await self._memberships.get_role(user_id, tenant_id)
        if role is None:
            raise _forbidden_vault_action(action, vault_id)

        if role in (OrgRole.OWNER, OrgRole.ADMIN):
            return AccessContext(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
                vault_permission=VaultPermission.ADMIN,
            )

        if role is OrgRole.MEMBER:
            if not _member_allows(action):
                raise _forbidden_vault_action(action, vault_id)
            return AccessContext(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
                vault_permission=VaultPermission.WRITE,
            )

        if role is OrgRole.VIEWER:
            if not _viewer_allows(action):
                raise _forbidden_vault_action(action, vault_id)
            return AccessContext(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
                vault_permission=VaultPermission.READ,
            )

        permission = await self._grants.get_permission(user_id, tenant_id, vault_id)
        if not _grant_allows(permission, action, role=role):
            raise _forbidden_vault_action(action, vault_id)

        return AccessContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            vault_permission=permission,
        )

    async def list_accessible_vault_ids(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID] | None:
        """None = unrestricted (owner/admin). List = grant-scoped vault IDs."""
        role = await self._memberships.get_role(user_id, tenant_id)
        if role is None:
            raise ForbiddenError("Access denied")
        if role in (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MEMBER, OrgRole.VIEWER):
            return None
        return await self._grants.list_vault_ids_for_user(user_id, tenant_id)

from __future__ import annotations

import pytest

from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.access.services import org_capabilities_for_role


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (
            OrgRole.OWNER,
            {
                "can_create_vaults": True,
                "can_manage_members": True,
                "can_manage_invitations": True,
                "can_read_audit": True,
            },
        ),
        (
            OrgRole.ADMIN,
            {
                "can_create_vaults": True,
                "can_manage_members": True,
                "can_manage_invitations": True,
                "can_read_audit": True,
            },
        ),
        (
            OrgRole.MEMBER,
            {
                "can_create_vaults": False,
                "can_manage_members": False,
                "can_manage_invitations": False,
                "can_read_audit": False,
            },
        ),
        (
            OrgRole.VIEWER,
            {
                "can_create_vaults": False,
                "can_manage_members": False,
                "can_manage_invitations": False,
                "can_read_audit": False,
            },
        ),
    ],
)
def test_org_capabilities_for_role(role: OrgRole, expected: dict[str, bool]) -> None:
    assert org_capabilities_for_role(role) == expected

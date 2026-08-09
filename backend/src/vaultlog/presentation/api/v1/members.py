from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from vaultlog.application.organizations.use_cases import ListMembers, RemoveMember
from vaultlog.domain.access.models import OrgRole
from vaultlog.presentation.dependencies import (
    Principal,
    StepUpPurpose,
    current_principal,
    get_list_members,
    get_remove_member,
    require_mfa_if_owner,
    require_step_up,
)

router = APIRouter(
    prefix="/members",
    tags=["members"],
    dependencies=[Depends(require_mfa_if_owner)],
)


class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: OrgRole
    created_at: str


@router.get(
    "",
    response_model=list[MemberResponse],
)
async def list_members(
    principal: Principal = Depends(current_principal),
    use_case: ListMembers = Depends(get_list_members),
) -> list[MemberResponse]:
    members = await use_case.execute(principal.user_id, principal.tenant_id)
    return [
        MemberResponse(
            membership_id=member.membership_id,
            user_id=member.user_id,
            email=member.email,
            role=member.role,
            created_at=member.created_at.isoformat(),
        )
        for member in members
    ]


@router.delete(
    "/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    membership_id: uuid.UUID,
    principal: Principal = Depends(require_step_up(StepUpPurpose.REMOVE_MEMBER)),
    use_case: RemoveMember = Depends(get_remove_member),
) -> None:
    await use_case.execute(
        principal.to_actor(),
        membership_id,
        step_up_proven=True,
    )

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from vaultlog.application.organizations.use_cases import (
    AcceptInvitation,
    CreateInvitation,
    ListInvitations,
    PreviewInvitation,
    RevokeInvitation,
)
from vaultlog.domain.access.models import OrgRole
from vaultlog.domain.identity.rate_limits import (
    INVITE_ACCEPT_IP_CAPACITY,
    INVITE_ACCEPT_IP_WINDOW_SECONDS,
    INVITE_CREATE_CAPACITY,
    INVITE_CREATE_WINDOW_SECONDS,
    INVITE_PREVIEW_IP_CAPACITY,
    INVITE_PREVIEW_IP_WINDOW_SECONDS,
)
from vaultlog.presentation.dependencies import (
    Principal,
    current_principal,
    get_accept_invitation,
    get_create_invitation,
    get_list_invitations,
    get_preview_invitation,
    get_revoke_invitation,
    rate_limit,
    require_mfa_if_owner,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: OrgRole = Field(description="admin, member, or viewer")


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: OrgRole
    expires_at: str
    created_at: str


class InvitationPreviewResponse(BaseModel):
    organization_name: str
    role: OrgRole
    email_masked: str


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=12, max_length=128)


@router.post(
    "",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_mfa_if_owner),
        Depends(
            rate_limit(
                "invite-create",
                capacity=INVITE_CREATE_CAPACITY,
                window_seconds=INVITE_CREATE_WINDOW_SECONDS,
                fail_closed=True,
                by="user",
            )
        ),
    ],
)
async def create_invitation(
    body: InvitationCreateRequest,
    principal: Principal = Depends(current_principal),
    use_case: CreateInvitation = Depends(get_create_invitation),
) -> InvitationResponse:
    if body.role is OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot invite owner role",
        )
    invitation = await use_case.execute(principal.to_actor(), body.email, body.role)
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at.isoformat(),
        created_at=invitation.created_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[InvitationResponse],
    dependencies=[Depends(require_mfa_if_owner)],
)
async def list_invitations(
    principal: Principal = Depends(current_principal),
    use_case: ListInvitations = Depends(get_list_invitations),
) -> list[InvitationResponse]:
    invitations = await use_case.execute(principal.user_id, principal.tenant_id)
    return [
        InvitationResponse(
            id=inv.id,
            email=inv.email,
            role=inv.role,
            expires_at=inv.expires_at.isoformat(),
            created_at=inv.created_at.isoformat(),
        )
        for inv in invitations
    ]


@router.delete(
    "/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_mfa_if_owner)],
)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    use_case: RevokeInvitation = Depends(get_revoke_invitation),
) -> None:
    await use_case.execute(principal.to_actor(), invitation_id)


@router.get(
    "/preview",
    response_model=InvitationPreviewResponse,
    dependencies=[
        Depends(
            rate_limit(
                "invite-preview",
                capacity=INVITE_PREVIEW_IP_CAPACITY,
                window_seconds=INVITE_PREVIEW_IP_WINDOW_SECONDS,
                fail_closed=True,
            )
        )
    ],
)
async def preview_invitation(
    token: str = Query(min_length=1),
    use_case: PreviewInvitation = Depends(get_preview_invitation),
) -> InvitationPreviewResponse:
    preview = await use_case.execute(token)
    return InvitationPreviewResponse(
        organization_name=preview.organization_name,
        role=preview.role,
        email_masked=preview.email_masked,
    )


@router.post(
    "/accept",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            rate_limit(
                "invite-accept",
                capacity=INVITE_ACCEPT_IP_CAPACITY,
                window_seconds=INVITE_ACCEPT_IP_WINDOW_SECONDS,
                fail_closed=True,
            )
        )
    ],
)
async def accept_invitation(
    body: AcceptInvitationRequest,
    use_case: AcceptInvitation = Depends(get_accept_invitation),
) -> None:
    await use_case.execute(body.token, body.password)

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from vaultlog.application.vaults.use_cases import (
    CreateVault,
    DeleteVault,
    GetVault,
    ListGrants,
    ListVaults,
    ManageGrant,
    UpdateVault,
)
from vaultlog.domain.access.models import OrgRole, VaultPermission
from vaultlog.presentation.dependencies import (
    Principal,
    StepUpPurpose,
    current_principal,
    get_create_vault,
    get_delete_vault,
    get_get_vault,
    get_list_grants,
    get_list_vaults,
    get_manage_grant,
    get_update_vault,
    require_step_up,
)

router = APIRouter(prefix="/vaults", tags=["vaults"])


class VaultCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class VaultUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class VaultResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: str


class GrantRequest(BaseModel):
    membership_id: uuid.UUID
    permission: VaultPermission


class GrantResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    org_role: OrgRole
    permission: VaultPermission
    granted_at: str


@router.post("", response_model=VaultResponse, status_code=status.HTTP_201_CREATED)
async def create_vault(
    body: VaultCreateRequest,
    principal: Principal = Depends(current_principal),
    use_case: CreateVault = Depends(get_create_vault),
) -> VaultResponse:
    view = await use_case.execute(
        principal.to_actor(),
        body.name,
        body.description,
    )
    return VaultResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        created_at=view.created_at.isoformat(),
    )


@router.get("", response_model=list[VaultResponse])
async def list_vaults(
    principal: Principal = Depends(current_principal),
    use_case: ListVaults = Depends(get_list_vaults),
) -> list[VaultResponse]:
    views = await use_case.execute(principal.user_id, principal.tenant_id)
    return [
        VaultResponse(
            id=view.id,
            name=view.name,
            description=view.description,
            created_at=view.created_at.isoformat(),
        )
        for view in views
    ]


@router.get("/{vault_id}", response_model=VaultResponse)
async def get_vault(
    vault_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    use_case: GetVault = Depends(get_get_vault),
) -> VaultResponse:
    view = await use_case.execute(principal.user_id, principal.tenant_id, vault_id)
    return VaultResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        created_at=view.created_at.isoformat(),
    )


@router.patch("/{vault_id}", response_model=VaultResponse)
async def update_vault(
    vault_id: uuid.UUID,
    body: VaultUpdateRequest,
    principal: Principal = Depends(current_principal),
    use_case: UpdateVault = Depends(get_update_vault),
) -> VaultResponse:
    if body.name is None and "description" not in body.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    clear_description = "description" in body.model_fields_set and body.description is None
    view = await use_case.execute(
        principal.to_actor(),
        vault_id,
        name=body.name,
        description=body.description,
        clear_description=clear_description,
    )
    return VaultResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        created_at=view.created_at.isoformat(),
    )


@router.delete("/{vault_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vault(
    vault_id: uuid.UUID,
    principal: Principal = Depends(require_step_up(StepUpPurpose.DELETE_VAULT)),
    use_case: DeleteVault = Depends(get_delete_vault),
) -> None:
    await use_case.execute(
        principal.to_actor(),
        vault_id,
        step_up_proven=True,
    )


@router.get(
    "/{vault_id}/grants",
    response_model=list[GrantResponse],
    summary="List explicit vault grants",
    description=(
        "Returns explicit vault_grant rows only. Members and viewers with org-wide "
        "access may not appear here."
    ),
)
async def list_grants(
    vault_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    use_case: ListGrants = Depends(get_list_grants),
) -> list[GrantResponse]:
    grants = await use_case.execute(principal.to_actor(), vault_id)
    return [
        GrantResponse(
            membership_id=grant.membership_id,
            user_id=grant.user_id,
            email=grant.email,
            org_role=grant.org_role,
            permission=grant.permission,
            granted_at=grant.granted_at.isoformat(),
        )
        for grant in grants
    ]


@router.post("/{vault_id}/grants", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_grant(
    vault_id: uuid.UUID,
    body: GrantRequest,
    principal: Principal = Depends(current_principal),
    use_case: ManageGrant = Depends(get_manage_grant),
) -> None:
    await use_case.grant(
        principal.to_actor(),
        vault_id,
        body.membership_id,
        body.permission,
    )


@router.delete("/{vault_id}/grants/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(
    vault_id: uuid.UUID,
    membership_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    use_case: ManageGrant = Depends(get_manage_grant),
) -> None:
    await use_case.revoke(
        principal.to_actor(),
        vault_id,
        membership_id,
    )

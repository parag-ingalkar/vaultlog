from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vaultlog.application.organizations.use_cases import GetOrganization
from vaultlog.domain.access.models import OrgRole
from vaultlog.presentation.dependencies import (
    Principal,
    current_principal,
    get_get_organization,
)

router = APIRouter(prefix="/organization", tags=["organization"])


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    caller_role: OrgRole


@router.get("", response_model=OrganizationResponse)
async def get_organization(
    principal: Principal = Depends(current_principal),
    use_case: GetOrganization = Depends(get_get_organization),
) -> OrganizationResponse:
    org = await use_case.execute(principal.to_actor())
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        caller_role=org.caller_role,
    )

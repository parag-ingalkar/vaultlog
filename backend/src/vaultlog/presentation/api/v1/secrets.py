from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from vaultlog.application.secrets.use_cases import (
    CreateSecret,
    DeleteSecret,
    ListSecrets,
    RevealSecret,
    RotateSecret,
)
from vaultlog.presentation.dependencies import (
    Principal,
    StepUpPurpose,
    current_principal,
    get_create_secret,
    get_delete_secret,
    get_list_secrets,
    get_reveal_secret,
    get_rotate_secret,
    require_step_up,
)

router = APIRouter(prefix="/vaults/{vault_id}/secrets", tags=["secrets"])


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=10_000)
    description: str | None = Field(default=None, max_length=1000)


class SecretMetaResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_at: str
    updated_at: str


class RevealResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    value: str


class RotateSecretRequest(BaseModel):
    value: str = Field(min_length=1, max_length=10_000)


@router.post("", response_model=SecretMetaResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    vault_id: uuid.UUID,
    body: SecretCreateRequest,
    principal: Principal = Depends(current_principal),
    use_case: CreateSecret = Depends(get_create_secret),
) -> SecretMetaResponse:
    view = await use_case.execute(
        principal.user_id,
        principal.tenant_id,
        vault_id,
        body.name,
        body.value,
        body.description,
    )
    return SecretMetaResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        current_version=view.current_version,
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
    )


@router.get("", response_model=list[SecretMetaResponse])
async def list_secrets(
    vault_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    use_case: ListSecrets = Depends(get_list_secrets),
) -> list[SecretMetaResponse]:
    views = await use_case.execute(principal.user_id, principal.tenant_id, vault_id)
    return [
        SecretMetaResponse(
            id=view.id,
            name=view.name,
            description=view.description,
            current_version=view.current_version,
            created_at=view.created_at.isoformat(),
            updated_at=view.updated_at.isoformat(),
        )
        for view in views
    ]


@router.post("/{secret_id}/reveal", response_model=RevealResponse)
async def reveal_secret(
    vault_id: uuid.UUID,
    secret_id: uuid.UUID,
    response: Response,
    version: int | None = None,
    principal: Principal = Depends(current_principal),
    use_case: RevealSecret = Depends(get_reveal_secret),
) -> RevealResponse:
    meta, plaintext, revealed_version = await use_case.execute(
        principal.user_id,
        principal.tenant_id,
        vault_id,
        secret_id,
        version,
    )
    response.headers["Cache-Control"] = "no-store"
    return RevealResponse(
        id=meta.id,
        name=meta.name,
        version=revealed_version,
        value=plaintext,
    )


@router.post("/{secret_id}/rotate", response_model=SecretMetaResponse)
async def rotate_secret(
    vault_id: uuid.UUID,
    secret_id: uuid.UUID,
    body: RotateSecretRequest,
    principal: Principal = Depends(current_principal),
    use_case: RotateSecret = Depends(get_rotate_secret),
) -> SecretMetaResponse:
    view = await use_case.execute(
        principal.user_id,
        principal.tenant_id,
        vault_id,
        secret_id,
        body.value,
    )
    return SecretMetaResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        current_version=view.current_version,
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
    )


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    vault_id: uuid.UUID,
    secret_id: uuid.UUID,
    principal: Principal = Depends(require_step_up(StepUpPurpose.DELETE_SECRET)),
    use_case: DeleteSecret = Depends(get_delete_secret),
) -> None:
    await use_case.execute(
        principal.user_id,
        principal.tenant_id,
        vault_id,
        secret_id,
        step_up_proven=True,
    )

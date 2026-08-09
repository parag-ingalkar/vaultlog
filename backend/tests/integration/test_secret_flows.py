from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from tests.integration.fixtures.audit import make_actor, tenant_uow_factory
from tests.integration.fixtures.constants import TENANT_B
from tests.integration.fixtures.vaults import (
    ADMIN_USER,
    MEMBER_MEMBERSHIP,
    MEMBER_USER,
    ORG_ID,
    OWNER_USER,
    VAULT_ID,
    seed_rbac_tenant,
)
from vaultlog.application.audit.use_cases import RecordAccessDenial
from vaultlog.application.secrets.use_cases import (
    CreateSecret,
    DeleteSecret,
    RevealSecret,
    RotateSecret,
)
from vaultlog.application.vaults.use_cases import CreateVault, ManageGrant
from vaultlog.domain.access.exceptions import ForbiddenError, NotFoundError
from vaultlog.domain.access.models import VaultPermission
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.models import TenantKeyVersionModel
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.infrastructure.security.vault_crypto import (
    AesGcmSecretEncryptor,
    LocalKEKProvider,
)
from vaultlog.shared.config import get_settings

PASSWORD = "correct horse battery"
settings = get_settings()


def _unique_email(prefix: str = "secret") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def _tenant_factory(app_engine, tenant_id: uuid.UUID):
    return tenant_uow_factory(app_engine, tenant_id)


def _secret_use_cases(app_engine, tenant_id: uuid.UUID):
    factory = _tenant_factory(app_engine, tenant_id)
    record_denial = RecordAccessDenial(factory)
    kek = LocalKEKProvider(settings)
    encryptor = AesGcmSecretEncryptor()
    return (
        CreateSecret(factory, kek, encryptor, record_denial),
        RevealSecret(factory, kek, encryptor, record_denial),
        RotateSecret(factory, kek, encryptor, record_denial),
        DeleteSecret(factory, kek, encryptor, record_denial),
    )


def _create_vault(app_engine, tenant_id: uuid.UUID) -> CreateVault:
    factory = _tenant_factory(app_engine, tenant_id)
    return CreateVault(factory, RecordAccessDenial(factory))


async def test_register_provisions_tenant_key(
    register_user,
    login_user,
    app_engine,
) -> None:
    email = _unique_email("dek")
    await register_user.execute(email, PASSWORD, "Acme")
    result = await login_user.execute(email, PASSWORD, "pytest")
    assert result.pair is not None
    tenant_id = TokenService(settings).verify_access_token(result.pair.access_token).tenant_id

    factory = build_session_factory(app_engine)
    async with factory() as session:
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        row = await session.scalar(
            select(TenantKeyVersionModel).where(
                TenantKeyVersionModel.tenant_id == tenant_id,
                TenantKeyVersionModel.status == "active",
            )
        )
        assert row is not None
        assert row.version == 1


async def test_create_and_reveal_secret(
    register_user,
    login_user,
    app_engine,
) -> None:
    email = _unique_email("crud")
    user_id = await register_user.execute(email, PASSWORD, "Acme")
    login = await login_user.execute(email, PASSWORD, "pytest")
    assert login.pair is not None
    tenant_id = TokenService(settings).verify_access_token(login.pair.access_token).tenant_id

    vault = await _create_vault(app_engine, tenant_id).execute(
        make_actor(user_id, tenant_id),
        "Secrets",
        None,
    )

    create, reveal, _, _ = _secret_use_cases(app_engine, tenant_id)
    meta = await create.execute(
        make_actor(user_id, tenant_id),
        vault.id,
        "api-key",
        "hunter2",
        "test secret",
    )
    assert meta.current_version == 1

    _, plaintext, version = await reveal.execute(
        make_actor(user_id, tenant_id),
        vault.id,
        meta.id,
        None,
    )
    assert plaintext == "hunter2"
    assert version == 1


async def test_rotate_secret_preserves_history(
    register_user,
    login_user,
    app_engine,
) -> None:
    email = _unique_email("rotate")
    user_id = await register_user.execute(email, PASSWORD, "Acme")
    login = await login_user.execute(email, PASSWORD, "pytest")
    assert login.pair is not None
    tenant_id = TokenService(settings).verify_access_token(login.pair.access_token).tenant_id

    vault = await _create_vault(app_engine, tenant_id).execute(
        make_actor(user_id, tenant_id),
        "Rotate",
        None,
    )
    create, reveal, rotate, _ = _secret_use_cases(app_engine, tenant_id)

    meta = await create.execute(make_actor(user_id, tenant_id), vault.id, "k", "v1", None)
    await rotate.execute(make_actor(user_id, tenant_id), vault.id, meta.id, "v2")
    rotated = await rotate.execute(make_actor(user_id, tenant_id), vault.id, meta.id, "v3")

    _, p1, _ = await reveal.execute(make_actor(user_id, tenant_id), vault.id, meta.id, 1)
    _, p2, _ = await reveal.execute(make_actor(user_id, tenant_id), vault.id, meta.id, 2)
    _, p3, _ = await reveal.execute(make_actor(user_id, tenant_id), vault.id, meta.id, None)
    assert p1 == "v1"
    assert p2 == "v2"
    assert p3 == "v3"
    assert rotated.current_version == 3


@pytest.fixture()
async def rbac_tenant(owner_engine, app_engine):
    await seed_rbac_tenant(owner_engine, app_engine)


async def test_member_read_grant_can_reveal_not_rotate(app_engine, rbac_tenant) -> None:
    manage = ManageGrant(
        _tenant_factory(app_engine, ORG_ID),
        RecordAccessDenial(_tenant_factory(app_engine, ORG_ID)),
    )
    await manage.grant(
        make_actor(ADMIN_USER, ORG_ID),
        VAULT_ID,
        MEMBER_MEMBERSHIP,
        VaultPermission.READ,
    )

    create, reveal, rotate, delete = _secret_use_cases(app_engine, ORG_ID)
    meta = await create.execute(
        make_actor(ADMIN_USER, ORG_ID),
        VAULT_ID,
        "shared",
        "value",
        None,
    )
    _, plaintext, _ = await reveal.execute(
        make_actor(MEMBER_USER, ORG_ID),
        VAULT_ID,
        meta.id,
        None,
    )
    assert plaintext == "value"

    with pytest.raises(ForbiddenError):
        await rotate.execute(make_actor(MEMBER_USER, ORG_ID), VAULT_ID, meta.id, "new")

    with pytest.raises(ForbiddenError):
        await delete.execute(
            make_actor(MEMBER_USER, ORG_ID),
            VAULT_ID,
            meta.id,
            step_up_proven=True,
        )


async def test_cross_tenant_secret_is_not_found(app_engine, rbac_tenant) -> None:
    create, _reveal, _, _ = _secret_use_cases(app_engine, ORG_ID)
    meta = await create.execute(
        make_actor(OWNER_USER, ORG_ID),
        VAULT_ID,
        "isolated",
        "hidden",
        None,
    )

    _, reveal_b, _, _ = _secret_use_cases(app_engine, TENANT_B)
    with pytest.raises(NotFoundError):
        await reveal_b.execute(
            make_actor(OWNER_USER, TENANT_B),
            VAULT_ID,
            meta.id,
            None,
        )


async def test_delete_requires_step_up_in_service(app_engine, rbac_tenant) -> None:
    create, _, _, delete = _secret_use_cases(app_engine, ORG_ID)
    meta = await create.execute(
        make_actor(OWNER_USER, ORG_ID),
        VAULT_ID,
        "del",
        "x",
        None,
    )
    with pytest.raises(ForbiddenError):
        await delete.execute(
            make_actor(OWNER_USER, ORG_ID),
            VAULT_ID,
            meta.id,
            step_up_proven=False,
        )

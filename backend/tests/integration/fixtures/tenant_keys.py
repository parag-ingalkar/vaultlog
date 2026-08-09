"""Provision tenant encryption keys for integration seed data."""

from __future__ import annotations

import uuid

from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.application.secrets.use_cases import ProvisionTenantKey
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from vaultlog.infrastructure.security.vault_crypto import (
    AesGcmSecretEncryptor,
    LocalKEKProvider,
)
from vaultlog.shared.config import get_settings


async def provision_tenant_encryption_key(app_engine, tenant_id: uuid.UUID) -> None:
    factory = build_session_factory(app_engine)
    settings = get_settings()

    def uow_factory(tenant: uuid.UUID) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(factory, TenantContext(tenant_id=tenant))

    provision = ProvisionTenantKey(
        uow_factory,
        LocalKEKProvider(settings),
        AesGcmSecretEncryptor(),
    )
    await provision.execute(tenant_id)

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from vaultlog.application.ports.unit_of_work import UnitOfWork
from vaultlog.domain.access.ports import (
    MembershipAccessPort,
    VaultAccessPort,
    VaultGrantAccessPort,
)
from vaultlog.domain.audit.ports import AuditLedgerPort
from vaultlog.domain.secrets.ports import (
    SecretRepository,
    SecretVersionRepository,
    TenantKeyRepository,
)
from vaultlog.domain.vaults.ports import VaultGrantRepository, VaultRepository


class TenantUnitOfWork(UnitOfWork, Protocol):
    vaults: VaultRepository
    vault_grants: VaultGrantRepository
    membership_access: MembershipAccessPort
    vault_access: VaultAccessPort
    grant_access: VaultGrantAccessPort
    secrets: SecretRepository
    secret_versions: SecretVersionRepository
    tenant_keys: TenantKeyRepository
    audit: AuditLedgerPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

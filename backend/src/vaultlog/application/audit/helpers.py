from __future__ import annotations

from vaultlog.application.ports.tenant_unit_of_work import TenantUnitOfWork
from vaultlog.domain.audit.services import AuditService


def build_audit_service(uow: TenantUnitOfWork) -> AuditService:
    return AuditService(uow.audit)

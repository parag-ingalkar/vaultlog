# ADR 0002: Separate database roles for migrations, application, and admin

- Status: Accepted
- Date: 2026-07-29

## Context

PostgreSQL RLS is bypassed by superusers and (unless forced) by table owners.
If the application connects with the same role that runs migrations, RLS
provides no real isolation guarantee.

## Decision

- vaultlog_owner: owns schema, runs migrations via Alembic, and is the only
  role with `BYPASSRLS`. The application uses it solely through the isolated
  `IdentityUnitOfWork` for pre-tenant operations (register, login, refresh,
  logout) where membership/organization must be reachable without a tenant GUC.
- vaultlog_app: NOBYPASSRLS, DML grants only, used by the FastAPI application
  for all tenant-scoped work.
- Break-glass admin access beyond identity remains a separate future concern;
  do not reuse the identity UoW for tenant data.

## Consequences

- Every migration creating a table must also GRANT to vaultlog_app and add
  ENABLE/FORCE ROW LEVEL SECURITY plus a tenant_isolation policy.
- Local development seeds fixture data through the owner role.
- The app role cannot create tables, preventing privilege drift at runtime.

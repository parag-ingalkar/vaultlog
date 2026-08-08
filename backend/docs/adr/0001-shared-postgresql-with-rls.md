# ADR 0001: Use shared PostgreSQL with Row-Level Security

- Status: Accepted
- Date: 2026-07-29

## Context

VaultLog is a multi-tenant SaaS application. Organizations must never access
another organization's vaults, secret metadata, encrypted secret material, or
audit records.

## Decision

Use one shared PostgreSQL database and schema. Every tenant-owned table will
contain a non-null `tenant_id` column. PostgreSQL Row-Level Security will enforce
tenant isolation using a transaction-scoped tenant identifier set by the
application after JWT validation.

## Consequences

- The app database role must not have `BYPASSRLS`.
- The application must set tenant context for every transaction.
- Every tenant-owned table requires RLS enabled, forced, and tested.
- RLS policies are owned by idempotent scripts in `scripts/rls/policies/`,
  applied automatically after Alembic upgrades (see ADR 0004).
- Database migrations must be reviewed as security-sensitive changes.
- RLS supplements application-level authorization; it does not replace it.

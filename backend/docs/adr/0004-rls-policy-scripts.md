# ADR 0004: Decouple RLS policies into idempotent scripts

- Status: Accepted
- Date: 2026-08-07

## Context

Tenant isolation requires `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`,
and a `tenant_isolation` policy on every tenant-owned table. Embedding this DDL in
each Alembic revision couples security to schema history, blocks clean
`--autogenerate`, and duplicates the same policy text across revisions.

## Decision

- Alembic revisions own schema only: tables, indexes, constraints, and `GRANT` to
  `vaultlog_app`. Downgrades drop tables; no `DROP POLICY` in revisions.
- One idempotent SQL file per tenant-owned table lives in
  `scripts/rls/policies/<table>.sql`, generated from `scripts/rls/template.sql`.
- `scripts/rls/apply.py` reconciles desired policy state on the migration connection
  **only after upgrades** (`is_upgrade_revision` in `alembic/env.py`).
- Policy apply is idempotent: `DROP POLICY IF EXISTS` + `CREATE POLICY` on each run.
- Alembic hook: skip policy files whose table does not exist (warn). Standalone
  `python -m scripts.rls.apply`: fail if any policy file targets a missing table.
- New tables: `uv run python -m scripts.rls.new_policy <table>`; register in
  `TENANT_TABLES`.

## Consequences

- Existing revisions that embed RLS remain in history; scripts are the source of
  truth going forward.
- `alembic downgrade` does not run policy apply; dropped tables lose policies via
  `DROP TABLE`. Surviving tables keep their policies until the next upgrade.
- Offline `alembic upgrade --sql` emits schema only; RLS scripts are not included.
- `TENANT_TABLES` in `apply.py` must stay aligned with tenant-owned tables for
  drift detection in tests.
- Grants remain in migrations for now.
- Removing a tenant table: drop table in migration, delete policy file, update
  `TENANT_TABLES` in the same change.

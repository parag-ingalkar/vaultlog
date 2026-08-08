# Migration security checklist

## Tenant-owned table (RLS required)

- [ ] Table has non-null, indexed `tenant_id` (or is the tenant table with `id` as tenant key).
- [ ] `GRANT SELECT, INSERT, UPDATE, DELETE` (minimum needed) to `vaultlog_app` in the Alembic revision.
- [ ] Policy script at `scripts/rls/policies/<table>.sql` via `uv run python -m scripts.rls.new_policy <table>`.
- [ ] Table listed in `TENANT_TABLES` in `scripts/rls/apply.py`.
- [ ] Do **not** embed `ENABLE/FORCE ROW LEVEL SECURITY` or `CREATE POLICY` in the revision.
- [ ] Do **not** embed `DROP POLICY` in downgrade — `DROP TABLE` removes policies.
- [ ] Cross-tenant integration test added or updated.

RLS scripts run automatically after `alembic upgrade` only. To re-apply after editing a policy file: `uv run python -m scripts.rls.apply`.

## Global identity table (no RLS)

Examples: `app_user`, `auth_session`, `refresh_token`.

- [ ] No RLS; access only via `IdentityUnitOfWork` (owner / `BYPASSRLS`).
- [ ] `GRANT` DML to `vaultlog_app` where the app role needs access.
- [ ] No policy script in `scripts/rls/policies/`.

## Removing a tenant-owned table

- [ ] Migration drops the table (no `DROP POLICY` needed).
- [ ] Delete `scripts/rls/policies/<table>.sql`.
- [ ] Remove table from `TENANT_TABLES` in `scripts/rls/apply.py`.
- [ ] Update or remove related integration tests.

Downgrade is safe: tables and policies are removed by the migration; RLS apply is not run on downgrade.

## Integration tests

Integration tests use database `vaultlog_test` (see `tests/integration/fixtures/README.md`). Never run integration tests against `vaultlog`.

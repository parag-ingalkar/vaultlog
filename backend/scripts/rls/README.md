# RLS policy scripts

Tenant isolation policies live here—not in Alembic revisions. Schema migrations create tables and `GRANT`; these scripts enable and force RLS plus the `tenant_isolation` policy.

## How it works

| Action | Schema (Alembic) | RLS (scripts) |
|--------|------------------|---------------|
| `alembic upgrade` | Creates/alters tables, grants | Re-applies all policy files for existing tables |
| `alembic downgrade` | Drops tables (policies drop with them) | **Not run** — no policy re-apply |
| `python -m scripts.rls.apply` | — | Re-applies all policies; **fails** if a policy file targets a missing table |

Policy files are idempotent: each run does `DROP POLICY IF EXISTS` then `CREATE POLICY`, so template edits apply safely on the next upgrade or standalone run.

## Adding a tenant-owned table

1. Add the SQLAlchemy model (`tenant_id` indexed and `NOT NULL`, or org-style where the tenant key is `id`).
2. Autogenerate and review the schema migration only:
   ```bash
   uv run alembic revision --autogenerate -m "add vault_grant"
   ```
3. In the revision, include `GRANT SELECT, INSERT, UPDATE, DELETE ON <table> TO vaultlog_app`. Do **not** add `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, or `CREATE POLICY`.
4. Create the policy script:
   ```bash
   uv run python -m scripts.rls.new_policy vault_grant
   # organization-style tenant key:
   uv run python -m scripts.rls.new_policy organization --column id
   ```
5. Add the table name to `TENANT_TABLES` in `apply.py`.
6. Apply:
   ```bash
   uv run alembic upgrade head
   ```
7. Add or extend cross-tenant integration tests.

## Adding a global (non-tenant) table

Examples: `app_user`, `auth_session`, `refresh_token`.

1. Autogenerate schema migration with `GRANT` as needed.
2. **No** policy script. Access only via `IdentityUnitOfWork` (owner / `BYPASSRLS` path).
3. `uv run alembic upgrade head` — no RLS step for this table.

## Removing a tenant-owned table

1. Autogenerate or write a migration that drops the table. Do **not** add `DROP POLICY` — `DROP TABLE` removes attached policies.
2. Delete `policies/<table>.sql`.
3. Remove the table from `TENANT_TABLES` in `apply.py`.
4. `uv run alembic downgrade` (if needed locally) then `upgrade head`, or just `upgrade head` on deploy.

Downgrade drops the table and its policies. Policy apply is skipped on downgrade, so a leftover policy file only produces a warning until you delete it.

## Re-apply policies without a schema migration

After editing `template.sql` or an existing policy file:

```bash
uv run python -m scripts.rls.apply
```

## Layout

- `template.sql` — placeholders `{{table}}` and `{{tenant_column}}`
- `policies/<table>.sql` — rendered, idempotent SQL (DROP + CREATE)
- `new_policy.py` — copy template into `policies/`
- `apply.py` — execute policy files; `TENANT_TABLES` registry for drift tests

## See also

- [Migration security checklist](../../docs/migration-checklist.md)
- [ADR 0004: RLS policy scripts](../../docs/adr/0004-rls-policy-scripts.md)

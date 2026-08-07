# Migration security checklist

For every migration that creates or alters a tenant-owned table:

- [ ] Table has non-null, indexed `tenant_id` (or is itself the tenant table).
- [ ] `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` executed.
- [ ] `tenant_isolation` policy created with fail-closed
      `NULLIF(current_setting('app.current_tenant', true), '')::uuid`.
- [ ] Policy has both `USING` and `WITH CHECK`.
- [ ] `GRANT SELECT, INSERT, UPDATE, DELETE` (minimum needed) to `vaultlog_app`.
- [ ] Downgrade drops policies before tables.
- [ ] Cross-tenant integration test added or updated.

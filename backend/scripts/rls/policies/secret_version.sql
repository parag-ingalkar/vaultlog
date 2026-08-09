ALTER TABLE secret_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE secret_version FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON secret_version;

CREATE POLICY tenant_isolation ON secret_version
USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

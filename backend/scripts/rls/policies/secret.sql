ALTER TABLE secret ENABLE ROW LEVEL SECURITY;
ALTER TABLE secret FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON secret;

CREATE POLICY tenant_isolation ON secret
USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

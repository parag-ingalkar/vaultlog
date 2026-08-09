ALTER TABLE invitation ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitation FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON invitation;

CREATE POLICY tenant_isolation ON invitation
USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

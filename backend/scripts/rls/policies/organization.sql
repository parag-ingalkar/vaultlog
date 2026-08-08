ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON organization;

CREATE POLICY tenant_isolation ON organization
USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

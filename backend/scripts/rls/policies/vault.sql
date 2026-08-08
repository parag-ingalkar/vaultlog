ALTER TABLE vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON vault;

CREATE POLICY tenant_isolation ON vault
USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

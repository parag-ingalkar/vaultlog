ALTER TABLE vault_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault_grant FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON vault_grant;

CREATE POLICY tenant_isolation ON vault_grant
USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

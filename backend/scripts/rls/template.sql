ALTER TABLE {{table}} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {{table}} FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON {{table}};

CREATE POLICY tenant_isolation ON {{table}}
USING ({{tenant_column}} = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
WITH CHECK ({{tenant_column}} = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- Executed once when the data volume is first initialized.
-- POSTGRES_USER/POSTGRES_DB create the bootstrap superuser and database.

CREATE ROLE vaultlog_owner LOGIN PASSWORD 'vaultlog_owner_password' BYPASSRLS;
CREATE ROLE vaultlog_app LOGIN PASSWORD 'vaultlog_app_password' NOBYPASSRLS;

-- Ownership transfer: the owner role owns the database, not the app role.
ALTER DATABASE vaultlog OWNER TO vaultlog_owner;

GRANT CONNECT ON DATABASE vaultlog TO vaultlog_app;

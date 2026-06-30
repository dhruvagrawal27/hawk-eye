-- Hawk-Eye Postgres bootstrap (PLATFORM-2/32).
-- Runs once on first init. Creates the separate governance DB alongside the app DB.
-- App schema (cases/users) is owned by DATABASE; PLATFORM owns the governance DB schema
-- (governance/db/schema.sql), applied at runtime by governance-api / `make seed-governance`.

SELECT 'CREATE DATABASE governance'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'governance')\gexec

-- Read-only role the governance-api / dashboard can use (least privilege, Part 19.3).
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'governance_ro') THEN
    CREATE ROLE governance_ro LOGIN PASSWORD 'governance_ro_dev_pw';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE governance TO governance_ro;

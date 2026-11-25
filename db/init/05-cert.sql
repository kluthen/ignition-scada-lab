-- Runs once, when the pgdata volume is first created (and again, harmlessly,
-- from scripts/db_apply.py): psql's \gexec makes it idempotent.
-- Empty database for the Core Certification sandbox gateway (gateway-cert):
-- transaction groups, recipes, report data sources... without touching mes.
SELECT 'CREATE DATABASE cert' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'cert')\gexec

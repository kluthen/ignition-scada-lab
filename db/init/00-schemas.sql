-- Runs once, when the pgdata volume is first created.
-- Separate schemas keep Ignition's own tables apart from the MES model.
CREATE SCHEMA IF NOT EXISTS historian;   -- Ignition SQL Historian / tag history
CREATE SCHEMA IF NOT EXISTS alarms;      -- alarm journal, audit log
CREATE SCHEMA IF NOT EXISTS mes;         -- orders, production, downtime, traceability

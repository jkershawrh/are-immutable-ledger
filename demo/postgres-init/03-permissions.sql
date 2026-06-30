-- Create a restricted application role that has INSERT+SELECT only on ledger entries.
-- The ledger service connects as this role and verifies it cannot UPDATE/DELETE.
CREATE ROLE ledger_app WITH LOGIN PASSWORD 'ledger_app';

GRANT USAGE ON SCHEMA are_ledger TO ledger_app;
GRANT INSERT, SELECT ON are_ledger.ledger_entries TO ledger_app;
GRANT INSERT, SELECT, UPDATE ON are_ledger.ledger_write_outbox TO ledger_app;
GRANT INSERT, SELECT, UPDATE ON are_ledger.ledger_chain_tips TO ledger_app;

-- Explicitly do NOT grant UPDATE or DELETE on ledger_entries to ledger_app.
-- The ledger service verifies this at startup.

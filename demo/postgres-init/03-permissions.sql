-- Enforce append-only: grant INSERT+SELECT only, no UPDATE/DELETE on ledger entries.
-- The ledger service verifies these permissions at startup and refuses to start
-- if UPDATE or DELETE is available.
GRANT USAGE ON SCHEMA are_ledger TO ledger;
GRANT INSERT, SELECT ON are_ledger.ledger_entries TO ledger;
GRANT INSERT, SELECT, UPDATE ON are_ledger.ledger_write_outbox TO ledger;
GRANT INSERT, SELECT, UPDATE ON are_ledger.ledger_chain_tips TO ledger;

REVOKE UPDATE, DELETE ON are_ledger.ledger_entries FROM ledger;

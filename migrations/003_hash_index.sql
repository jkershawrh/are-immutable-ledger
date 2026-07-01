-- Index for proof receipt verification: lookup by (entry_type, entry_hash)
-- Used by VerifyProof RPC for fast hash-based receipt validation
CREATE INDEX IF NOT EXISTS idx_ledger_entry_hash
  ON are_ledger.ledger_entries(entry_type, entry_hash);

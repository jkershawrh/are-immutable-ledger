-- Optional input_hash: SHA-256 of the payload that was checked.
-- Allows downstream verifiers to confirm a receipt covers the exact
-- payload they're looking at (catches payload transformation between hops).
ALTER TABLE are_ledger.ledger_entries
  ADD COLUMN IF NOT EXISTS input_hash VARCHAR(64) NULL;

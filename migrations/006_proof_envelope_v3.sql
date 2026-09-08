-- Version every stored entry hash so old and new proof envelopes can coexist.
-- Existing rows were written with V2, which did not bind the optional writer
-- signature, signer key reference, or attestation report. New writes use V3.

ALTER TABLE are_ledger.ledger_entries
  ADD COLUMN IF NOT EXISTS hash_version VARCHAR(64)
  DEFAULT 'ARE_LEDGER_ENTRY_HASH_V2';

UPDATE are_ledger.ledger_entries
SET hash_version = 'ARE_LEDGER_ENTRY_HASH_V2'
WHERE hash_version IS NULL;

ALTER TABLE are_ledger.ledger_entries
  ALTER COLUMN hash_version SET NOT NULL,
  ALTER COLUMN hash_version SET DEFAULT 'ARE_LEDGER_ENTRY_HASH_V3';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ledger_entries_hash_version_check'
      AND conrelid = 'are_ledger.ledger_entries'::regclass
  ) THEN
    ALTER TABLE are_ledger.ledger_entries
      ADD CONSTRAINT ledger_entries_hash_version_check
      CHECK (hash_version IN (
        'ARE_LEDGER_ENTRY_HASH_V2',
        'ARE_LEDGER_ENTRY_HASH_V3'
      ));
  END IF;
END $$;

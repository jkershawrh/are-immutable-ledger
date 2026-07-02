-- Writer signature + attestation support for identity and runtime proof.
-- signature: opaque bytes (Ed25519, ECDSA, RSA — writer's choice)
-- signer_key_reference: key identifier (SPIFFE SVID, DID, key ID — verifier resolves)
-- attestation_report: opaque bytes (SGX quote, SEV-SNP report, RATS EAT — verifier checks)
-- All optional: unsigned/unattested entries continue to work.

ALTER TABLE are_ledger.ledger_entries
  ADD COLUMN IF NOT EXISTS writer_signature BYTEA NULL;

ALTER TABLE are_ledger.ledger_entries
  ADD COLUMN IF NOT EXISTS signer_key_reference VARCHAR(255) NULL;

ALTER TABLE are_ledger.ledger_entries
  ADD COLUMN IF NOT EXISTS attestation_report BYTEA NULL;

CREATE INDEX IF NOT EXISTS idx_ledger_signer
  ON are_ledger.ledger_entries(signer_key_reference)
  WHERE signer_key_reference IS NOT NULL;

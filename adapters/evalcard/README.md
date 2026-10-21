# Fabric evaluation-card adapter

Notarizes governed-agent-fabric evaluation cards into the immutable ledger and
verifies the resulting proof receipts. This makes a qualification run's
reporting artifact tamper-evident: the card digest is chained, and any later
edit to the card breaks the receipt binding.

## Contract

- The card shape is `fabric.evaluation-card/v1`, pinned at
  [`contracts/fabric-evaluation-card-v1.schema.json`](../../contracts/fabric-evaluation-card-v1.schema.json).
- `card_sha256` must match the card body (canonical JSON, sorted keys). It is
  used as both the ledger `idempotency_key` and the `input_hash`, so
  notarizing the same card twice cannot create two entries.
- Entries are written with `entry_type = fabric.evaluation-card.v1`,
  `agent_id = governed-agent-fabric`, `content_type = application/json`, the
  full canonical card as content, and `correlation_id` set to the card's
  `evaluation.source_id` (the plan or record id) for cross-system correlation.
- Cards whose `verdict.authorizes_execution` is not exactly `false` are
  refused: the ledger records evidence, it never grants authority.

## Usage

```sh
# Notarize a card (demo endpoint; standalone ledger uses :9092)
python3 adapters/evalcard/evalcard_to_ledger.py notarize \
  --card evaluation-card.json \
  --endpoint localhost:19292

# Verify the receipt later, optionally re-binding it to the card file
python3 adapters/evalcard/evalcard_to_ledger.py verify \
  --receipt evaluation-card.json.receipt.json \
  --card evaluation-card.json \
  --endpoint localhost:19292
```

`notarize` writes a create-only `fabric.evalcard-receipt/v1` receipt beside
the card (override with `--receipt-output`). `verify` calls the ledger's
`VerifyProof` and exits non-zero when the proof is invalid.

A valid fixture card lives in [`fixtures/evaluation-card.json`](fixtures/evaluation-card.json).

## Boundaries

- The adapter is not in the authorization path and grants no execution
  authority.
- A receipt proves the card bytes were recorded in a hash chain at a chain
  position and time. It does not prove the card's claims are true, that the
  qualification was sound, or that the capability is currently deployed.
- The card content is stored verbatim; sanitize cards before notarizing if
  your run artifacts contain sensitive material.

# Praxis PPE preview adapter

This reference adapter validates a producer-neutral
`praxis.ppe.audit.v1` decision, maps it to OCSF 6003, and requests an
immutable-ledger proof receipt. It implements the
[Praxis PPE–OCSF contract](../../contracts/praxis-ppe-ocsf-ledger-contract.md).

It is deliberately separate from the CPEX adapter. ContextForge/CPEX uses
`cpex.*`; Praxis/PPE uses `praxis.ppe.*`. This adapter replays a contract
fixture and does not claim to be a native plugin in a released Praxis build.

## Validate without a ledger

```bash
python3 -m pytest -q tests/test_praxis_ppe_adapter.py
```

The tests prove version rejection, field validation, secret/content rejection,
deterministic OCSF mapping, exact trace correlation, namespaced entry types,
idempotency-key mapping, and receipt submission.

The deliberately unsupported fixture provides an observable red result. The
gRPC channel is lazy, so contract rejection does not require a running ledger:

```bash
python3 adapters/praxis_ppe/ppe_to_ledger.py \
  --file adapters/praxis_ppe/fixtures/ppe-audit-v2-invalid.jsonl
# exits 1: unsupported schema_version
```

## Replay against a running ledger

From the repository root:

```bash
python3 adapters/praxis_ppe/ppe_to_ledger.py \
  --endpoint localhost:19292 \
  --source-id praxis-lab-dev \
  --file adapters/praxis_ppe/fixtures/ppe-audit-v1.jsonl
```

The ledger credential, if enabled, is read by the shared client from
`ARE_LEDGER_API_TOKEN`. Do not place it in the fixture or command line.

The command returns nonzero if JSON parsing, contract validation, or ledger
submission fails. It does not alter a PPE decision and must not be used to
authorize a request.

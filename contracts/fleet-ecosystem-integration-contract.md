# Fleet ecosystem ledger integration contract

This document defines the immutable-ledger boundary for the core fleet path:

`deepfield-fleet -> governed-cognitive-loop -> fleet-llm-d -> immutable ledger`

The producer repositories own their event and payload schemas. The ledger treats
`content` as opaque bytes, preserves the supplied metadata, and supplies durable
hash-chain evidence. It does not interpret a forecast, approve a decision
package, authorize a fleet action, or execute infrastructure changes.

## Trust and authorization boundary

A `ProofReceipt` proves that a matching entry was written and that its canonical
entry hash is valid. It is not a credential, capability, grant, passport, or
authorization decision. In particular:

- `VerifyProof.valid` means the stored entry matches its canonical hash.
- `VerifyChain.chain_valid` establishes linkage for an exact `entry_type` chain.
- `writer_signature`, `signer_key_reference`, and `attestation_report` are
  opaque values stored and returned by the ledger; the ledger does not verify
  them.
- Bearer tokens on the gRPC service or REST gateway authenticate access to that
  deployment. They do not authorize a fleet action.
- Fleet admission, approval, and execution authorization remain outside this
  service. A ledger entry may record the result of such a decision, but the
  receipt does not become the decision.

## Canonical gRPC contract

The authoritative protobuf contract is
[`proto/immutable_ledger.proto`](../proto/immutable_ledger.proto):

- package: `are.ledger.v1`
- service: `ImmutableLedgerService`
- write and receipt RPCs: `WriteEntry`, `IssueReceipt`
- lookup and query RPCs: `GetEntry`, `GetEntryByHash`, `QueryEntries`,
  `GetChainTip`
- verification RPCs: `VerifyEntry`, `VerifyProof`, `VerifyChain`

`WriteEntryRequest` carries these integration fields:

| Field | Meaning |
| --- | --- |
| `entry_type` | Producer-owned, versioned event type and exact ledger-chain key |
| `agent_id` | Producer-supplied actor or workload identity |
| `content` | Opaque payload bytes |
| `content_type` | Media type for `content` |
| `source_id` | Stable producer identity |
| `correlation_id` | Shared identifier joining forecast, decision, operation, and outcome |
| `idempotency_key` | Stable retry key scoped to `entry_type` |
| `input_hash` | Optional digest of the input or subject covered by the entry |
| signature fields | Optional opaque writer signature, key reference, and attestation |

`ProofReceipt` returns `entry_hash`, `entry_type`, `chain_position`,
`written_ts` (Unix milliseconds), `entry_id`, `input_hash`, and the optional
signature fields. Consumers must retain both `entry_hash` and `entry_type` for
`VerifyProof`; use `VerifyChain` separately when claiming chain integrity.

## REST compatibility gateway

The Flask gateway in `api/gateway.py` is an optional compatibility and UI
adapter. It is not a second version of the contract and does not expose
`/v1/ledger/*` routes.

| Operation | Route |
| --- | --- |
| Write entry | `POST /api/entries` |
| Issue proof receipt | `POST /api/receipts` |
| Query entries | `GET /api/entries` |
| Verify proof | `GET /api/receipts/verify?hash=<entry_hash>&type=<entry_type>` |
| Get by hash | `GET /api/entries/by-hash?hash=<entry_hash>&type=<entry_type>` |
| Verify one type chain | `GET /api/verify/<entry_type>` |
| Verify all discovered chains | `GET /api/verify` |

The REST write body uses the same snake-case field names as
`WriteEntryRequest`. Its `content` value is a UTF-8 string; arbitrary binary
content should use the canonical gRPC API. `GET /api/entries` accepts the gRPC
query field names, including Unix-millisecond `from_ts` and `to_ts`, and returns
a JSON array whose entries contain `input_hash`, parsed `content` (when JSON),
and `content_raw`. Shared deployments must configure `GATEWAY_API_TOKEN` and
place the gateway behind a TLS-aware boundary.

## Core-path correlation

All producers use the same opaque `correlation_id` for one decision lifecycle.
A typical sequence is:

1. `deepfield-fleet` publishes an advisory forecast or finding to GCL without
   writing the ledger directly.
2. `governed-cognitive-loop` records the resulting decision package.
3. `fleet-llm-d` records admitted operation transitions and the observed
   outcome.
4. An auditor queries by `correlation_id`, verifies each receipt, and verifies
   each exact `entry_type` chain.

Correlation establishes a reconstructable timeline; it does not imply that one
entry authorized another. Causal identifiers and domain evidence remain inside
the producer-owned payload contracts.

## Conformance evidence

`tests/fleet_ecosystem_contract.rs` exercises the existing in-memory service
through its public service methods. It proves that the ledger can retain
correlated DeepField-shaped evidence, decision, and fleet transition entries,
verify every proof receipt, query the shared correlation, and verify all
involved chains. The DeepField-shaped fixture is ledger conformance evidence;
it does not create a direct DeepField-to-ledger runtime path.

This is contract-level ledger evidence only. It does not claim that the four
repositories were assembled, deployed, or exercised against live clusters.

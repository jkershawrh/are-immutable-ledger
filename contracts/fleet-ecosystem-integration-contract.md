# Immutable ledger integration contract

This document defines the immutable-ledger boundary for all producer
integrations. The ledger treats `content` as opaque bytes, preserves the
supplied metadata, and supplies durable hash-chain evidence. It does not
interpret event payloads, approve decisions, authorize actions, or execute
infrastructure changes.

Two integration paths are currently defined:

- **Fleet ecosystem:** `deepfield-fleet -> governed-cognitive-loop -> fleet-llm-d -> immutable ledger`
- **CPEX / AuthBridge / Praxis:** policy enforcement and guardrail dedup
  via proof receipts

The producer repositories own their event and payload schemas. The conventions
in this contract — `entry_type` namespacing, `correlation_id` threading, proof
receipt propagation — apply to all integration paths.

## Trust and authorization boundary

A `ProofReceipt` proves that the ledger accepted and still contains a matching
writer assertion under its recorded hash version. It does not independently
prove the assertion is true or that the claimed check executed correctly. It
is not a credential, capability, grant, passport, or authorization decision.
In particular:

- `VerifyProof.valid` means the stored entry matches its canonical hash.
- `VerifyChain.chain_valid` establishes linkage for an exact `entry_type` chain.
- `writer_signature`, `signer_key_reference`, and `attestation_report` are
  opaque values stored and returned by the ledger. V3 binds the bytes into the
  canonical entry hash, but the ledger does not define the signature payload,
  resolve the key, validate the signature, or appraise the attestation.
- Bearer tokens on the gRPC service or REST gateway authenticate access to that
  deployment. They do not authorize a fleet action or policy decision.
- Authorization decisions (fleet admission, CPEX policy evaluation, AuthBridge
  access control) remain outside this service. A ledger entry may record the
  result of such a decision, but the receipt does not become the decision.

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
| `correlation_id` | Shared identifier joining related entries across systems |
| `idempotency_key` | Stable retry key scoped to `entry_type` |
| `input_hash` | Optional digest of the input or subject covered by the entry |
| signature fields | Optional opaque writer signature, key reference, and attestation |

`ProofReceipt` returns `entry_hash`, `entry_type`, `chain_position`,
`written_ts` (Unix milliseconds), `entry_id`, `input_hash`, and the optional
signature fields plus `hash_version`. Consumers must retain both `entry_hash`
and `entry_type` for `VerifyProof`; use `VerifyChain` separately when claiming
chain integrity. Consumers requiring bound signature or attestation evidence
must require V3 because legacy V2 hashes did not cover those fields.

## Entry type namespace convention

Each producer system uses a prefix to form independent, separately verifiable
hash chains:

| Prefix | Producer | Example entry types |
| --- | --- | --- |
| `io.srex.deepfield.*` | DeepField fleet | `io.srex.deepfield.forecast.v1` |
| `ai.llm-d.gcl.*` | Governed Cognitive Loop | `ai.llm-d.gcl.decision-package.v1` |
| `fleet.*` | Fleet operations | `fleet.operation.verified` |
| `cpex.*` | CPEX policy enforcement | `cpex.policy.allow`, `cpex.guardrail.pii_scan` |
| `authbridge.*` | AuthBridge sidecar | `authbridge.token.exchanged`, `authbridge.tool.denied` |
| `openshell.*` | NVIDIA OpenShell | `openshell.http_activity` |
| `kagenti.*` | Kagenti / OTEL | `kagenti.tool.call` |

The `entry_type` is both a semantic label and a performance boundary — each
type forms its own advisory-lock-serialized chain. Finer-grained types
distribute write load across more parallel chains.

## Concurrency and chain integrity

The ledger uses a PostgreSQL connection pool (`deadpool-postgres`, configurable
via `ARE_LEDGER_POOL_MAX_SIZE`, default 16). Writes to different `entry_type`
chains acquire separate connections and separate per-type advisory locks,
running truly in parallel.

Writes to the same `entry_type` chain serialize through a per-type
PostgreSQL advisory lock (SHA-256-derived 64-bit key). On contention, the write retries
with exponential backoff (10ms, 20ms, 40ms, ...) up to a configurable maximum
(`ARE_LEDGER_CHAIN_MAX_RETRIES`, default 10). If all retries exhaust, the chain
is temporarily halted and auto-recovers after a configurable timeout
(`ARE_LEDGER_CHAIN_HALT_RECOVERY_SECONDS`, default 60).

## REST compatibility gateway

The async gateway in `api/gateway.py` (FastAPI + uvicorn) is an optional
compatibility and UI adapter. It is not a second version of the contract
and does not expose `/v1/ledger/*` routes.

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
a paginated JSON object containing `entries`, `next_page_token`, and
`total_count`. Each entry contains `input_hash`, `hash_version`, parsed
`content` (when JSON), and `content_raw`. Shared deployments must configure
`GATEWAY_API_TOKEN` and place the gateway behind a TLS-aware boundary.

## Proof receipt propagation

Receipts solve the redundant-check problem in multi-hop architectures. An
enforcement point writes its decision to the ledger via `IssueReceipt` and
attaches the receipt to the forwarded request:

```
X-Proof-Receipt: base64({"h":"<entry_hash>","t":"<entry_type>","ih":"<input_hash>"})
```

The next hop calls `VerifyProof(entry_hash, entry_type)`. A `valid` response is
only the ledger-integrity check. Before reusing the result, the consumer must
also require an acceptable `hash_version`, verify the issuer signature and
trust chain, validate attestation if required, compare `input_hash` with the
current request, enforce freshness, check the policy/check version and scope,
and apply local authorization. If any requirement fails, the downstream hop
re-runs its check or rejects the request and may issue its own receipt.

See `demo/joint-cpex/scenarios/07-multi-hop-receipt-chain.sh` for an executable
example.

## Correlation

All producers use the same opaque `correlation_id` for one decision lifecycle.

### Fleet ecosystem correlation

1. `deepfield-fleet` publishes an advisory forecast or finding to GCL without
   writing the ledger directly.
2. `governed-cognitive-loop` records the resulting decision package.
3. `fleet-llm-d` records admitted operation transitions and the observed
   outcome.
4. An auditor queries by `correlation_id`, verifies each receipt, and verifies
   each exact `entry_type` chain.

### CPEX / AuthBridge correlation

1. AuthBridge runs a guardrail (PII scan) and issues a receipt.
2. CPEX/Praxis verifies the receipt, skips re-scan, evaluates policy, and
   issues its own receipt.
3. Both entries share the same `correlation_id` (request trace ID or session).
4. An auditor queries by `correlation_id` to see the full enforcement chain.

Correlation establishes a reconstructable timeline; it does not imply that one
entry authorized another. Causal identifiers and domain evidence remain inside
the producer-owned payload contracts.

## Conformance evidence

`tests/fleet_ecosystem_contract.rs` exercises the existing in-memory service
through its public service methods. It proves that the ledger can retain
correlated DeepField-shaped evidence, decision, and fleet transition entries,
verify every proof receipt, query the shared correlation, and verify all
involved chains.

`demo/joint-cpex/scenarios/01-07` exercise the CPEX/AuthBridge integration
through the REST gateway, demonstrating receipt issuance, verification,
cross-system correlation, and chain verification.

This is contract-level ledger evidence only. It does not claim that the
producer repositories were assembled, deployed, or exercised against live
clusters.

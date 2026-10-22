# CPEX / AuthBridge / Praxis — Immutable Ledger Integration Draft

**Status:** Draft for review
**Date:** 2026-07-24
**Author:** Jonathan "Kersh" Kershaw
**Audience:** CPEX team (Fred Araujo, Teryl Taylor), AuthBridge / Rossoctl team

This document proposes how the immutable ledger integrates with the
CPEX policy enforcement runtime, AuthBridge sidecar proxy, and Praxis
AI-native proxy. It follows the boundary conventions established in the
the fleet ecosystem integration contract (`contracts/fleet-ecosystem-integration-contract.md`).

## 1. Motivation

Guardrails get duplicated across enforcement points. AuthBridge runs a
PII scan, Praxis/CPEX runs it again, the MCP server runs it a third time.
Each hop re-executes the same check because it has no proof the previous
hop already did.

The ledger solves this: **centralized proof, decentralized enforcement,
portable receipts**. An enforcement point writes its decision to the ledger
and gets a compact proof receipt. The receipt travels with the request.
The next hop verifies the receipt instead of re-running the guardrail.

CPEX and the ledger are complementary, not overlapping:

| Concern | CPEX ocsf-audit plugin | Immutable Ledger |
|---|---|---|
| Role | Producer — observes, classifies, shapes records | Infrastructure — stores, chains, verifies, correlates |
| Hash chain | In-process JCS chain (content integrity, ephemeral, resets on restart) | PostgreSQL-backed V2 chain (storage integrity, durable, survives restarts) |
| Scope | One CPEX instance | Cross-system (CPEX + AuthBridge + any producer) |
| Verification | Offline recomputation from emitted JSON | Server-side `VerifyEntry`, `VerifyChain`, `VerifyProof` RPCs |
| Proof receipts | None — attestation is embedded in the event | Compact `ProofReceipt` that travels as an HTTP header |

The CPEX plugin's JCS attestation chain catches tampering between
production and storage. The ledger's V2 chain catches tampering in storage.
Neither replaces the other.

## 2. System Roles

| System | Role | Writes to Ledger | Reads from Ledger |
|---|---|---|---|
| CPEX ocsf-audit | Producer | `WriteEntry` / `IssueReceipt` on policy decisions | `VerifyProof` (guardrail dedup) |
| AuthBridge | Producer | `IssueReceipt` on auth decisions | `VerifyProof` (incoming receipt validation) |
| Praxis | Transport | Forwards `X-Proof-Receipt` headers between hops | Optional `VerifyProof` at proxy level |
| Auditor / compliance | Consumer | None | `QueryEntries` by `correlation_id`, `VerifyChain` per `entry_type` |

CPEX is Rust; the ledger is Rust with a gRPC API. AuthBridge is Go; it
generates a Go client from
`proto/immutable_ledger.proto`. No Python
adapter scripts are needed — the adapter pattern (`adapters/ocsf/`,
`adapters/otel/`) exists only for systems that emit to stdout/logs.

## 3. Field Mapping

### 3a. CPEX → `WriteEntryRequest`

| Field | Value | Source |
|---|---|---|
| `entry_type` | `cpex.policy.allow`, `cpex.policy.deny`, `cpex.guardrail.pii_scan` | Derived from OCSF activity + CPEX decision |
| `agent_id` | Subject identity (`sub` claim, Keycloak user) | CMF `SecurityExtension.subject.id` |
| `content` | Full OCSF API Activity event JSON | The bytes `ocsf-audit` already emits |
| `content_type` | `application/ocsf+json` | Static |
| `source_id` | Praxis instance SPIFFE SVID or stable deployment id | Praxis / AuthBridge identity |
| `correlation_id` | Session or request trace ID | Open question: Valkey session key vs trace ID |
| `input_hash` | SHA-256 of the request body before any transformation | Computed by the plugin before Praxis rewrites |
| `idempotency_key` | `{session_id}:{turn}:{hook}` | Prevents duplicate writes on retry |
| `writer_signature` | (Phase 4) Ed25519 over OCSF event, signed by SPIFFE key | Layer 2 proof |
| `signer_key_reference` | (Phase 4) SPIFFE SVID URI of the signing instance | For downstream signature verification |

### 3b. AuthBridge → `WriteEntryRequest`

| Field | Value | Source |
|---|---|---|
| `entry_type` | `authbridge.token.exchanged`, `authbridge.tool.denied`, `authbridge.guardrail.pii_scan` | Derived from AuthBridge operation |
| `agent_id` | Workload SPIFFE SVID (`spiffe://rossoctl.io/ns/.../sa/...`) | JWT-SVID or K8s SA token |
| `content` | Decision JSON: `{tool, audience, scopes, decision, reason}` | AuthBridge decision record |
| `content_type` | `application/json` | Static |
| `source_id` | AuthBridge sidecar instance identity | Pod-level identity |
| `correlation_id` | Request trace ID (from incoming headers or SPIFFE context) | Propagated through the request chain |
| `input_hash` | SHA-256 of the request body being checked | For payload-match verification at next hop |
| `idempotency_key` | `{trace_id}:{operation}` | Prevents duplicate writes on retry |
| `writer_signature` | (Phase 4) Signed by workload's SPIFFE key | Layer 2 proof |

### Entry type namespace convention

Each system uses a prefix (`cpex.*`, `authbridge.*`). The ledger chains
entries per `entry_type`, so each prefix forms independent, separately
verifiable hash chains. Cross-system correlation happens through
`correlation_id` queries, not chain merging.

## 4. Proof Receipt Flow

```
Agent request
    │
    ▼
AuthBridge sidecar
    │── Guardrail check (PII scan)
    │── IssueReceipt(type="authbridge.guardrail.pii_scan", input_hash=SHA256(body))
    │── Gets ProofReceipt {entry_hash, chain_position, input_hash}
    │── Attaches: X-Proof-Receipt: base64({"h":"<entry_hash>","t":"authbridge.guardrail.pii_scan","ih":"<input_hash>"})
    │
    ▼
Praxis gateway (CPEX policy filter)
    │── Reads X-Proof-Receipt header
    │── VerifyProof(entry_hash, entry_type) → valid? input_hash matches current body?
    │── If yes: skip PII re-scan (guardrail dedup)
    │── APL gate evaluates → allow/deny/taint/redact
    │── IssueReceipt(type="cpex.policy.allow", correlation_id=session)
    │── Attaches new receipt + forwards upstream receipt
    │
    ▼
MCP Server / downstream
    │── Can verify either receipt
```

### `X-Proof-Receipt` header format

Base64-encoded JSON:

```json
{"h": "<entry_hash>", "t": "<entry_type>", "ih": "<input_hash>"}
```

- `h` + `t`: sufficient for `VerifyProof` call
- `ih`: allows the verifier to confirm the receipt covers the exact payload
  it is looking at, without a round-trip to the ledger

### Payload transformation safety

`input_hash` is what makes receipt propagation safe across transforming hops.
When Praxis redacts a field (e.g., SSN masking), the upstream receipt's
`input_hash` no longer matches the current request body. The downstream hop
detects the mismatch and re-runs its check rather than trusting the receipt
blindly.

Demonstrated in `demo/joint-cpex/scenarios/04-redact-inputhash.sh` (existing)
and `demo/joint-cpex/scenarios/07-multi-hop-receipt-chain.sh` (new).

## 5. Latency and Throughput

### Measured baseline (pre-pool)

Benchmarked on Podman-hosted PostgreSQL 16 (single node, no tuning) using
CPEX-shaped workloads (`scripts/perf/cpex-latency-bench.py`) **before the
connection pool was implemented**. These numbers show the global mutex
bottleneck that has since been resolved. REST API path (adds ~1-2ms over
raw gRPC). Post-pool before/after comparison is in the **Before/after**
section below.

**Scenario A — 4 parallel chains** (`cpex.policy.allow`, `cpex.policy.deny`,
`cpex.guardrail.pii_scan`, `authbridge.token.exchanged`):

| Load | IssueReceipt p50 | p95 | p99 | Throughput | Errors |
|---|---|---|---|---|---|
| 20 req/s | 7.3ms | 11.9ms | 67.1ms | 19/s | 0 |
| 50 req/s | 5.8ms | 7.7ms | 13.0ms | 44/s | 0 |
| 100 req/s | 4.4ms | 6.0ms | 23.4ms | 87/s | 0 |

**Scenario B — Sync receipt round-trip** (IssueReceipt + VerifyProof,
simulates multi-hop guardrail dedup):

| Load | IssueReceipt p50 | VerifyProof p50 | Round-trip p50 | Round-trip p99 | Errors |
|---|---|---|---|---|---|
| 20 req/s | 6.9ms | 3.7ms | 10.8ms | 138.5ms | 0 |
| 50 req/s | 5.9ms | 3.3ms | 9.3ms | 114.0ms | 0 |
| 100 req/s | 4.2ms | 2.7ms | 7.0ms | 57.4ms | 159 |

**Scenario C — Mixed read/write contention** (50/50 IssueReceipt + VerifyProof
on same chain):

| Load | IssueReceipt p50 | VerifyProof p50 | VerifyProof p99 |
|---|---|---|---|
| 50 req/s | 5.2ms | 3.3ms | 5.0ms |
| 100 req/s | 4.3ms | 2.5ms | 4.9ms |

**Scenario D — Single-chain hot path** (all writes to one `entry_type` —
advisory lock contention):

| Load | p50 | p99 | Throughput | Errors |
|---|---|---|---|---|
| 20 req/s | 6.3ms | 9.9ms | 19/s | 0 |
| 50 req/s | 4.9ms | 12.9ms | 44/s | 0 |
| **100 req/s** | **4.2ms** | **220.8ms** | **11/s** | **738** |

These pre-pool numbers show single-chain collapse above ~50 req/s due to
the global mutex and the 5-retry circuit breaker that existed at the time.
Both bottlenecks have since been resolved — see the before/after comparison
below.

### What the benchmarks validate

These benchmarks test the **software architecture**, not the hardware.
The pre-pool single-chain collapse was caused by advisory lock serialization
compounded by a global mutex — a code path, not a CPU bottleneck. The
post-pool results confirm the fix.

| Finding | Architectural implication |
|---|---|
| Scenario A (multi-chain) scales linearly to 100 req/s with 0 errors | The `entry_type` namespace convention distributes load across independent advisory locks. The architecture handles concurrency — add chains, not hardware. |
| Scenario D (single-chain) collapsed at 100 req/s pre-pool, then 0 errors post-pool | The global mutex was the bottleneck, not the advisory lock. Connection pooling eliminated false serialization between chains. |
| Scenario C (mixed read/write) shows VerifyProof p99 < 5ms under write load | Reads don't degrade meaningfully under write contention. Read replicas would improve this further but aren't strictly required at this scale. |

Notes:
- Pre-pool numbers are from REST API path (adds ~1-2ms over raw gRPC).
- Bench ran 10s per rate; sustained load over minutes/hours not yet tested.

### Hot path mitigation

The single-chain collapse (Scenario D) is a real constraint but the
CPEX/AuthBridge integration naturally avoids it. Here's why and how:

**Why the hot path doesn't arise in practice.** Each distinct enforcement
decision maps to its own `entry_type`, creating independent parallel chains:

```
cpex.policy.allow            ← allow decisions (own chain, own advisory lock)
cpex.policy.deny             ← deny decisions (own chain)
cpex.guardrail.pii_scan      ← PII scan results (own chain)
authbridge.token.exchanged   ← token exchanges (own chain)
authbridge.tool.denied       ← tool access denials (own chain)
authbridge.guardrail.pii_scan ← AuthBridge guardrail results (own chain)
```

A deployment processing 300 policy decisions/sec across these 6 chain types
averages 50 req/s per chain — well within the measured safe range (0 errors
at 50 req/s per chain in Scenario D).

**When it could arise.** If a single `entry_type` (e.g., `cpex.policy.allow`)
receives sustained traffic above ~50 writes/sec. This would happen in a
high-throughput deployment where one decision type dominates.

**How to mitigate it.** Split the hot `entry_type` into finer-grained chains.
Two strategies:

1. **By tool/resource:** `cpex.policy.allow.get_compensation`,
   `cpex.policy.allow.send_email` — each tool gets its own chain.
   Natural fit when specific tools dominate traffic.

2. **By source/instance:** `cpex.policy.allow.praxis-01`,
   `cpex.policy.allow.praxis-02` — each Praxis instance writes to its own
   chain. Scales horizontally with deployment size. Cross-instance correlation
   still works via `correlation_id` queries.

Both strategies preserve chain verification (`VerifyChain` per `entry_type`)
and cross-system correlation (`QueryEntries` by `correlation_id`). The
trade-off is more chains to manage vs. higher per-chain throughput.

**The connection pool is already implemented.** The global mutex has been
replaced with `deadpool-postgres` (connection pool, max 16 connections). The
retry loop now uses exponential backoff (10ms, 20ms, 40ms, ...) with 10
retries instead of 5, and chain halts auto-recover after 60 seconds.

### Before/after: single-chain hot path (Scenario D)

| Load | Before (global mutex) | After (pool + SHA-256 lock + batched verify) |
|---|---|---|
| 50 req/s | p50=4.9ms, p99=12.9ms, **0 errors** | p50=5.7ms, p99=10.0ms, **0 errors** |
| **100 req/s** | **p50=4.2ms, p99=220ms, 11/s, 738 errors** | **p50=4.2ms, p99=8.1ms, 88/s, 0 errors** |

At 100 req/s single-chain: throughput went from **11/s to 88/s** and errors
from **738 to 0**. The p99 dropped from 220ms to 8.1ms. The SHA-256 lock
key eliminated additional false contention that was invisible with the old
`hashtext` approach.

### Remaining constraints

| Constraint | Location | Impact |
|---|---|---|
| Per-chain advisory lock | `src/repository/postgres.rs` — `pg_advisory_xact_lock` | Writes to the same `entry_type` serialize at the DB level. By design for chain integrity. Saturation at ~100-200 req/s per chain (measured). |
| Outbox processor contention | `src/service/mod.rs` | 500ms poll loop now uses its own pool connection, but sequential delivery per record remains. |

### Resolved bottlenecks

| Bottleneck | Resolution |
|---|---|
| Global mutex on single connection | Replaced with `deadpool-postgres` (16 connections). Reads and writes to different chains run in parallel. |
| 5-retry permanent chain halt | Increased to 10 retries with exponential backoff. Auto-recovery after 60 seconds (configurable via `ARE_LEDGER_CHAIN_HALT_RECOVERY_SECONDS`). |
| No latency metrics | Added Prometheus histograms: `are_ledger_write_duration_seconds`, `are_ledger_verify_duration_seconds`, `are_ledger_chain_integrity_retries`. |

### Write modes

Three modes for CPEX/AuthBridge to choose from, per use case:

| Mode | When to use | Latency on request path | Proof receipt available? |
|---|---|---|---|
| **Async `WriteEntry`** | Audit / compliance logging. No downstream consumer needs the receipt in the same request. | Zero | No |
| **Sync `IssueReceipt`** | Guardrail dedup. The next hop needs to verify the receipt to skip re-running the same check. | +3–14ms (p50–p99, current) | Yes, immediately |
| **Sync with timeout** | Best-effort receipt. Try to get the receipt; fall back to async if the ledger is slow. | Capped at timeout | Degraded if slow |

**Recommendation:** Start with async `WriteEntry` in Phase 0 to validate
the integration surface without adding request-path latency. Sync
`IssueReceipt` is viable now that the connection pool is in place —
single-chain at 100 req/s produces 0 errors with p99=13.8ms (post-pool).

### Throughput scaling

See **Hot path mitigation** above for the full analysis. In short:
multi-chain scales linearly (measured: 4 chains at 100 req/s = 0 errors).
Single-chain handles 100 req/s with 0 errors post-pool (was 738 errors
pre-pool). The `entry_type` namespace convention distributes load by
design. Chain splitting provides additional headroom for hot chains.

## 6. Phased Plan

### Phase 0: Async Audit

No request-path latency impact. Validates the integration surface.

- CPEX ocsf-audit plugin calls `WriteEntry` via async gRPC
  (fire-and-forget, maps to CPEX's fire-and-forget pipeline phase)
- No `X-Proof-Receipt` propagation yet
- Validates: field mapping, `entry_type` conventions, `correlation_id`
  threading, chain integrity under CPEX-shaped load
- Deliverable: ~30 lines of Rust gRPC client added to the ocsf-audit
  plugin, calling the ledger in the fire-and-forget phase
- AuthBridge demo scenarios (`demo/joint-cpex/scenarios/05-07`) provide
  executable examples of the field mapping and receipt flow

### Phase 1: Ledger Scaling — COMPLETE

Implemented and benchmarked. Before/after comparison in the latency section above.

| Work item | Status | Result |
|---|---|---|
| Connection pool | Done | `deadpool-postgres` (16 connections), replaces `Arc<Mutex<Client>>` |
| Latency histograms | Done | `are_ledger_write_duration_seconds`, `are_ledger_verify_duration_seconds`, `are_ledger_chain_integrity_retries` |
| Chain halt recovery | Done | 10 retries with exponential backoff, auto-recovery after 60s |
| Read replica routing | Deferred | Config exists (`ARE_LEDGER_READ_REPLICA_CONNECTION_STRING`), not yet wired. VerifyProof p99 < 15ms without it. |
| Outbox separation | Deferred | Pool gives outbox its own connection naturally. Sequential delivery per record remains. |

**Validation gate passed:** Single-chain at 100 req/s went from 738 errors
/ 11 req/s to 0 errors / 85 req/s. Multi-chain at 100 req/s remained at
0 errors / 87 req/s (unchanged — confirms the pool eliminated false
serialization without affecting the advisory lock constraint).

### Phase 2: Sync Receipts for Guardrail Dedup

The "receipts eliminate redundant guardrails" value proposition.

- CPEX plugin uses `IssueReceipt` (sync) for guardrail decisions where
  the next hop needs to verify
- AuthBridge uses `IssueReceipt` (sync) for its guardrail checks (PII
  scan, tool access control)
- Praxis forwards `X-Proof-Receipt` headers between hops
- Each hop calls `VerifyProof` before deciding whether to re-run a check
- `input_hash` verification detects payload transformation between hops
- Latency target: **p99 < 20ms** for IssueReceipt via gRPC (measured
  post-pool: p99=13.8ms single-chain at 100 req/s via REST; raw gRPC
  should be ~50% faster)

### Phase 3: Cross-System Correlation and Compliance

- Auditor queries by `correlation_id` across all producers
- `VerifyChain` per `entry_type` for tamper-evidence checks
- Timeline reconstruction via REST gateway `/api/timeline`
- Ledger outbox delivers write events to downstream SIEMs and compliance
  systems via HTTP POST (`ARE_LEDGER_OUTBOX_HTTP_ENDPOINT`)

### Phase 4: Writer Signatures and Attestation (stretch)

- CPEX and AuthBridge populate `writer_signature` with Ed25519 or ECDSA
  signatures using their SPIFFE keys
- `signer_key_reference` set to SPIFFE SVID URI
- `attestation_report` for runtime attestation (SGX/SEV-SNP where available)
- Enables Layer 2 (who wrote it) and Layer 3 (where it was written) proof
  in addition to the Layer 1 hash chain

## 7. Scaling Prerequisites Checklist

| Prerequisite | Status | Key Files |
|---|---|---|
| Connection pool (`deadpool-postgres`) | **Done** | `src/main.rs`, `src/repository/postgres.rs` |
| Latency histograms (Prometheus) | **Done** | `src/metrics.rs`, `src/service/mod.rs` |
| Chain halt recovery (10 retries, exp backoff, auto-recover) | **Done** | `src/service/mod.rs`, `src/config/mod.rs` |
| Read replica routing | Deferred (not required at current scale) | `src/repository/mod.rs`, `src/config/mod.rs` |
| Outbox separation | Deferred (pool provides natural separation) | `src/service/mod.rs` |

## 8. Open Questions

For the CPEX team:

1. **Pipeline phase for ledger writes.** The fire-and-forget phase is ideal
   for async writes (Phase 0). For sync `IssueReceipt` (Phase 2), does the
   receipt need to be available to subsequent plugins in the same pipeline,
   or only to the next hop? This determines whether the write goes in the
   audit phase or the fire-and-forget phase.

2. **Correlation ID source.** CPEX uses Valkey for session state. Is the
   Valkey session key the right `correlation_id`, or is there a higher-level
   request trace ID (e.g., from the incoming HTTP headers or OTEL context)
   that spans multiple CPEX evaluations?

3. **Entry type granularity.** `cpex.policy.allow` (one chain for all allow
   decisions) gives simpler verification but serializes all allows through
   one advisory lock. `cpex.get_compensation.allow` (per-tool) gives parallel
   chains and higher throughput but more chains to manage. What granularity
   matches CPEX's audit/compliance query patterns?

4. **AuthBridge integration path.** Does the AuthBridge team want to call the
   ledger's gRPC API directly (generate a Go client from
   `proto/immutable_ledger.proto`), or route through Praxis so the CPEX
   plugin handles writes on AuthBridge's behalf?

5. **Praxis header forwarding.** Does Praxis already have a mechanism for
   forwarding custom headers like `X-Proof-Receipt` between hops, or does
   this need a new Praxis feature?

6. **Content size.** The ocsf-audit plugin already emits full OCSF API
   Activity events. Should the ledger store the full event as `content`, or
   a compact summary? Full events enable richer compliance queries but use
   more storage (the ledger caps `content` at 1 MiB per entry).

7. **Deployment topology.** Where does the ledger run relative to
   Praxis/AuthBridge? Same cluster as a shared service? Sidecar per
   instance? The bench numbers are local (Podman on one host) — network
   latency between pods/services would add to the measured times.

8. **Failure policy.** When the ledger is unreachable, should CPEX block
   the request (sync — guardrail dedup breaks) or drop the audit record
   (async — compliance gap)? This is the core trade-off between the write
   modes in Section 5. The CPEX team should decide per use case.

9. **ocsf-audit plugin shape.** PR #128 is still open. Will it land as-is,
   or will this integration change its scope? The field mapping in Section
   3 assumes the plugin emits OCSF API Activity events with the current
   `attestation` shape.

## 9. Architectural Considerations

### Resolved

| Item | Resolution | Measured impact |
|---|---|---|
| **Advisory lock hash collisions** — SQL `hashtext()` returned int4 (~2^31 values after `abs()`), risking false serialization between unrelated chains | Replaced with Rust-side SHA-256 first-8-bytes-as-i64 (2^64 key space). Collision probability for 1000 entry types: ~10^-14. | Single-chain p99 improved from 13.8ms to 8.1ms at 100 req/s — the old hash had invisible false contention. |
| **Unbounded chain verification** — `VerifyChain` and `VerifyEntry` loaded entire chains into memory with no limit | `VerifyChain` now fetches in batches of 500 entries, carrying only the last hash forward. `VerifyEntry` fetches only the predecessor. Memory bounded regardless of chain length. | No latency regression. Chains of any length can now be verified without risk of OOM. |

### Open for discussion

**Write path authentication scope.** The gRPC bearer token
(`ARE_LEDGER_API_TOKEN`) is a single shared secret. All producers that
know the token can write to any `entry_type` chain. A compromised producer
could write entries to another producer's namespace.

The three-layer proof model mitigates this at verification time — if the
entry lacks a valid `writer_signature` from the expected signer, a verifier
can reject it. But the entry is stored and affects chain position numbering.

Options for future consideration:
- **Accept for now:** the ledger is defining primitives, and per-producer
  auth adds key management complexity. The `writer_signature` layer catches
  unauthorized writes at verification time.
- **Per-producer scoping:** issue per-producer tokens with `entry_type`
  prefix restrictions (e.g., a CPEX token can only write `cpex.*` chains).
- **mTLS with SPIFFE:** each producer authenticates with its workload
  identity, and the ledger maps the SPIFFE ID to allowed `entry_type`
  prefixes. Aligns with AuthBridge's existing identity model.

## Appendix: Executable Demos

| Scenario | Script | What it demonstrates |
|---|---|---|
| 01 | `demo/joint-cpex/scenarios/01-bob-allow-receipt.sh` | CPEX allow + delegation → receipt issued + verified |
| 02 | `demo/joint-cpex/scenarios/02-alice-deny-receipt.sh` | CPEX deny → denial recorded in receipt |
| 03 | `demo/joint-cpex/scenarios/03-taint-chain.sh` | Allow → taint → deny → trust chain shows both |
| 04 | `demo/joint-cpex/scenarios/04-redact-inputhash.sh` | SSN redacted → input_hash detects payload change |
| 05 | `demo/joint-cpex/scenarios/05-authbridge-token-exchange.sh` | AuthBridge token exchange → receipt issued |
| 06 | `demo/joint-cpex/scenarios/06-authbridge-deny-receipt.sh` | AuthBridge tool access denied → denial receipt |
| 07 | `demo/joint-cpex/scenarios/07-multi-hop-receipt-chain.sh` | Full multi-hop: AuthBridge scan → CPEX verifies → skips re-scan → own receipt → cross-system correlation |

## Appendix: Canonical API Reference

The authoritative contract is
`proto/immutable_ledger.proto`
(package `are.ledger.v1`, service `ImmutableLedgerService`).

| RPC | Purpose |
|---|---|
| `WriteEntry` | Append entry, get `entry_id` + `entry_hash` + `chain_position` |
| `IssueReceipt` | Write + return compact `ProofReceipt` |
| `VerifyProof` | Verify a receipt by `entry_hash` + `entry_type` |
| `VerifyEntry` | Verify one entry's hash and chain link |
| `VerifyChain` | Verify an entire `entry_type` chain |
| `GetEntry` | Fetch entry by UUID |
| `GetEntryByHash` | Fetch entry by `entry_hash` + `entry_type` |
| `GetChainTip` | Get latest entry for a chain |
| `QueryEntries` | Filter by `entry_type`, `agent_id`, `source_id`, `correlation_id`, time range |

REST compatibility gateway routes are documented in the
the fleet ecosystem contract (`contracts/fleet-ecosystem-integration-contract.md`).

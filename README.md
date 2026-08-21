# Immutable Ledger for Agentic Systems

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Tamper-evident evidence infrastructure for agentic systems. Hash-chained entries show whether stored assertions were changed after acceptance. Portable proof receipts let downstream services retrieve and validate those assertions under an explicit trust policy. Cross-system queries correlate independently supplied events without pretending that correlation proves identity, causality, or truth.

> **A receipt is evidence that a writer submitted a particular assertion. Reusing that evidence is safe only after the consumer validates the issuer, signature, payload binding, freshness, policy/check version, and local authorization requirements.**

## What It Does

The ledger answers four questions for any agentic system:

1. **What was asserted?** Append-only event storage with per-type hash chains.
2. **Was the stored assertion changed?** SHA-256 hash chaining with version-aware verification.
3. **Is there reusable evidence for this check?** Proof receipts retrieve a bound assertion; downstream policy decides whether it is sufficient or the check must run again.
4. **Can you correlate across systems?** Query by agent ID, correlation ID, source, time range, or entry type across independent writers.

## The Universal Contract

One gRPC call. Your identity. Your event format. Chained and verifiable.

```protobuf
// Core write + audit
rpc WriteEntry(WriteEntryRequest) returns (WriteEntryResponse);

// Proof receipts — runtime trust propagation
rpc IssueReceipt(WriteEntryRequest) returns (ProofReceipt);
rpc VerifyProof(VerifyProofRequest) returns (VerifyProofResponse);
rpc GetEntryByHash(GetEntryByHashRequest) returns (GetEntryResponse);

// Chain verification + query
rpc VerifyEntry(VerifyEntryRequest) returns (VerifyEntryResponse);
rpc VerifyChain(VerifyChainRequest) returns (VerifyChainResponse);
rpc QueryEntries(QueryEntriesRequest) returns (QueryEntriesResponse);
```

No shared identity system required. No event format standardization required. Each system keeps its own IDs and its own event schema. The ledger chains entries per `entry_type`, so each source maintains an independent, verifiable hash chain.

## How It Works

- **Append-only** - database constraints enforce no UPDATE/DELETE on ledger entries. Startup verification confirms permissions.
- **Per-type hash chains** - each `entry_type` forms its own SHA-256 chain. Independent verification per source system.
- **Versioned canonical proof envelope** - V3 hashes commit to entry ID, metadata, content, idempotency key, input hash, optional signature/key-reference/attestation bytes, chain position, timestamp, and previous hash using length-delimited fields. Historical V2 entries remain verifiable with their original rules.
- **Concurrent-safe** - connection pool (`deadpool-postgres`, configurable max size) with per-`entry_type` PostgreSQL advisory locks. Writes to different chains run in parallel. Integrity violations trigger exponential backoff retry (up to 10 attempts, configurable) with auto-recovery after 60 seconds.
- **Idempotent** - optional idempotency keys prevent duplicate entries on retry; reusing a key with different content or metadata returns a conflict.
- **Cross-system queries** - `QueryEntries` filters by agent_id, correlation_id, source_id, entry_type prefix, and time range. One query returns entries from all sources for the same agent or request.
- **Hardened admin surface** - `/shutdownz` is disabled unless `ARE_LEDGER_SHUTDOWN_TOKEN` is set and requires a bearer token when enabled. gRPC bearer-token auth can be enabled with `ARE_LEDGER_API_TOKEN`.
- **Health & verification** - `/healthz` for liveness, `/readyz` checks database connectivity and background chain verification result, `/verifyz` returns detailed JSON verification status. Background verifier runs every 5 minutes by default.
- **Proof receipts** - `IssueReceipt` writes an entry and returns its persisted proof material. `VerifyProof` validates the stored canonical hash by hash and type without knowing the entry ID. It does not verify that the asserted check actually ran or was correct.
- **Writer evidence** - optional `writer_signature` (opaque bytes) + `signer_key_reference` (key ID, SPIFFE SVID, DID). V3 binds both into the entry hash, but the ledger does not define the signed payload, resolve the key, validate its trust chain, or verify the signature. Consumers must do that work.
- **Attestation evidence** - optional `attestation_report` (opaque bytes such as an SGX quote, SEV-SNP report, or RATS EAT token). V3 binds the bytes into the entry hash; consumers still validate format, endorsement chain, measurements, nonce/freshness, and policy.

## Three Layers of Proof

```
Layer 1: entry_hash            → stored envelope was not modified (ledger verifies)
Layer 2: writer_signature      → writer-supplied identity evidence (consumer verifies)
         signer_key_reference  → which key to use
Layer 3: attestation_report    → runtime evidence (consumer verifies against its trust policy)
```

All optional. All backward compatible. All identity-neutral — the ledger stores opaque bytes for Ed25519, ECDSA, SPIFFE SVIDs, SGX quotes, or any format the writer uses.

## Proof Receipts

Receipts can reduce redundant checks in multi-hop agentic architectures, but only when each consumer's policy accepts the evidence. When AuthBridge reports a guardrail result, it issues a receipt. The MCP Gateway validates the ledger proof plus the issuer evidence, current payload binding, freshness, check/policy version, audience, and purpose. It skips the check only if all required validations succeed.

```
AuthBridge runs guardrail
  → IssueReceipt(entry_type="guardrail.pii_scan", content={result: "clean"})
  → Gets ProofReceipt {entry_hash: "abc123...", chain_position: 42}
  → Attaches header: X-Proof-Receipt: base64({h:"abc123...", t:"guardrail.pii_scan"})
  → Forwards request

MCP Gateway receives request
  → Reads X-Proof-Receipt
  → VerifyProof(entry_hash="abc123...", entry_type="guardrail.pii_scan")
  → Response: {valid: true, agent_id: "authbridge", written_ts: ...}
  → Applies local receipt policy; skips only if every required check passes
```

Receipts are not credentials and do not grant authority. They prove that the ledger accepted and still contains a particular writer assertion under the stored hash version. They do not independently prove that a check ran, that its implementation was sound, that its result is current, or that the writer was honest. V3 commits to the full stored proof envelope; consumers must inspect `hash_version` and may reject legacy V2 receipts when signature or attestation binding is required.

## Performance

Benchmarked on Podman-hosted PostgreSQL 16 (single node, no tuning) using CPEX-shaped workloads via REST API (`scripts/perf/cpex-latency-bench.py`):

| Scenario | p50 | p99 | Throughput | Errors |
|---|---|---|---|---|
| IssueReceipt (4 parallel chains, 100 req/s) | 4.4ms | 57.6ms | 87/s | 0 |
| IssueReceipt (single chain, 100 req/s) | 4.2ms | 8.1ms | 88/s | 0 |
| VerifyProof (under write load, 100 req/s) | 2.8ms | 6.6ms | — | 0 |
| Receipt round-trip (IssueReceipt + VerifyProof, 50 req/s) | 8.0ms | 13.0ms | — | 0 |

Raw gRPC numbers (no REST overhead): WriteEntry p50=1.7ms p99=4.3ms ~520/sec, VerifyProof p50=0.6ms p99=1.7ms ~1,400/sec.

### Known Scale Considerations

| Concern | Current behavior | Mitigation path |
|---|---|---|
| **Advisory lock contention** | Writes to the same `entry_type` serialize via SHA-256-derived advisory locks. Single-chain: 88/s at 100 req/s with 0 errors. | Use distinct `entry_type` per source. Parallel chains scale linearly. Split hot chains by tool or instance. |
| **Chain verification on long chains** | VerifyChain walks chains in batches of 500 entries (bounded memory). Verification checkpoints not yet implemented. | Add checkpoints for long-chain skip-ahead. Streaming already prevents OOM. |
| **Storage growth** | Each entry stores full content bytes (up to 1 MiB). High-volume systems generate significant storage. | Content compression or content-addressed storage. Raw TTL deletion is unsupported because it breaks retained chain history; see `docs/retention-and-archival.md` for checkpointed archival requirements. |
| **gRPC message size** | QueryEntries can return large result sets. Default 4MB gRPC limit hit at ~3K entries. | Pagination (already implemented). Client must page through results. |

## Quick Start

```bash
cd demo
make up        # Start ledger + postgres
make smoke     # Write sample entries and verify chains
make demo      # Full cross-system demo with OpenShell + Kagenti
```

## Evidence & Metrics

The repository keeps the proof surface close to the code:

- `docs/oss-boundary-and-hardening-status.md` defines what this ledger can and cannot establish and lists the remaining enterprise gaps.
- `docs/retention-and-archival.md` defines why raw TTL deletion is unsafe and what a future archival protocol must preserve.
- `tests/EVIDENCE_MATRIX.md` summarizes automated, live, and not-yet-automated coverage.
- `tests/evidence-results.json` records the latest evidence runner output.
- `tests/SECURITY_TESTING.md` documents red-team and hardening checks.
- `contracts/fleet-ecosystem-integration-contract.md` defines the proof-only boundary
  and canonical API mapping for deepfield-fleet, governed-cognitive-loop, and
  fleet-llm-d integration.
- `proof-explorer/proof.py verify --all` requests stored-chain verification through the public API; `tests/run_evidence.py` also reconstructs a canonical entry hash independently.

The checked-in evidence snapshot records `146/146` automated checks GREEN for the commit and environment named in that artifact. It is historical evidence, not a guarantee that the current checkout or a new deployment is green. Re-run the applicable commands below and retain the resulting commit, configuration, and environment metadata for release evidence. The matrix keeps design-level/manual items YELLOW until they are automated in `tests/run_evidence.py`.

Useful local verification commands:

```bash
cargo test --all --locked
cargo clippy --all-targets --all-features --locked -- -D warnings
python tests/run_evidence.py
python proof-explorer/proof.py verify --all
```

The service exposes Prometheus metrics at `/metrics` on `ARE_LEDGER_METRICS_PORT`:

- `are_ledger_write_total` — write attempts by outcome (ok, invalid, error)
- `are_ledger_write_duration_seconds` — write latency histogram
- `are_ledger_verify_duration_seconds` — verification latency histogram
- `are_ledger_chain_integrity_retries` — retry attempts per write due to chain contention
- `are_ledger_chain_verify_failure_total` — chain verification detected invalid link or hash
- `are_outbox_publish_failure_total` — outbox HTTP publish failures
- `are_ledger_chain_integrity_valid` — background verifier result (1 = all chains valid, 0 = failure detected)

The standalone binary can deliver committed outbox events to an HTTP event sink. Set `ARE_LEDGER_OUTBOX_HTTP_ENDPOINT` to enable delivery, optionally set `ARE_LEDGER_OUTBOX_HTTP_BEARER_TOKEN`, and use `ARE_LEDGER_OUTBOX_HTTP_TIMEOUT_SECONDS` to override the 10-second request timeout. Each request contains the stored JSON payload plus `Idempotency-Key` (the outbox ID) and `X-Ledger-Entry-ID` headers. Successful 2xx responses mark the row `DELIVERED`; transport errors and non-2xx responses leave it `PENDING` for retry. Records are permanently marked `FAILED` after `ARE_LEDGER_OUTBOX_MAX_RETRIES` attempts (default 10) with exponential backoff. Consumers must deduplicate by `Idempotency-Key` because delivery is at least once. When the endpoint is unset, publishing is disabled and rows remain `PENDING`.

All configuration is via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `ARE_LEDGER_DB_CONNECTION_STRING` | *(required)* | PostgreSQL connection string (supports `sslmode=require` for TLS) |
| `ARE_LEDGER_GRPC_PORT` | 9092 | gRPC server listen port |
| `ARE_LEDGER_HEALTH_PORT` | 8080 | Health/readiness HTTP server port |
| `ARE_LEDGER_METRICS_PORT` | 8083 | Prometheus metrics HTTP server port |
| `ARE_LEDGER_MAX_CONTENT_SIZE_BYTES` | 1048576 | Maximum entry content size (1 MiB) |
| `ARE_LEDGER_POOL_MAX_SIZE` | 16 | PostgreSQL connection pool max size |
| `ARE_LEDGER_CHAIN_MAX_RETRIES` | 10 | Retry attempts per write before chain halt |
| `ARE_LEDGER_CHAIN_HALT_RECOVERY_SECONDS` | 60 | Auto-recovery timeout for halted chains |
| `ARE_LEDGER_VERIFY_INTERVAL_SECONDS` | 300 | Background chain verification interval (0 = disabled) |
| `ARE_LEDGER_OUTBOX_MAX_RETRIES` | 10 | Max publish attempts before marking outbox record FAILED |
| `ARE_LEDGER_GENESIS_HASH_INPUT` | `ARE_LEDGER_GENESIS` | Seed value for genesis hash of new chains |
| `ARE_LEDGER_API_TOKEN` | *(unset)* | Bearer token for gRPC auth (disabled when unset) |
| `ARE_LEDGER_SHUTDOWN_TOKEN` | *(unset)* | Bearer token for `/shutdownz` (endpoint hidden when unset) |

Hash compatibility note: migration 006 labels existing rows as V2 and new rows as V3. Verification dispatches by each row's `hash_version`; unknown versions fail closed. V2 did not bind `writer_signature`, `signer_key_reference`, or `attestation_report`, so consumers requiring those properties must reject V2 receipts or re-issue evidence under V3. Do not relabel or re-hash historical rows in place.

## Security Notes

For shared deployments, set `sslmode=require` or `sslmode=verify-full` in `ARE_LEDGER_DB_CONNECTION_STRING` for encrypted Postgres connections (rustls-based, no OpenSSL dependency). Put the gRPC listener behind TLS/mTLS-capable infrastructure and set `ARE_LEDGER_API_TOKEN`; clients can pass the token explicitly or through the same environment variable. Set `ARE_LEDGER_SHUTDOWN_TOKEN` only for controlled graceful-shutdown drills, and call `/shutdownz` with `Authorization: Bearer <token>`.

The REST gateway requires `GATEWAY_API_TOKEN` and will not start without it, because it writes ledger evidence. For local development set `GATEWAY_ALLOW_UNAUTHENTICATED=true` to run it open deliberately. It binds to `127.0.0.1`, runs with debug disabled, and only allows localhost Vite origins unless `GATEWAY_CORS_ORIGINS` is set. `/healthz` is exempt from authentication so container probes do not need the token. Keep it behind TLS/auth-aware infrastructure, and only widen `GATEWAY_HOST` or CORS origins intentionally.

## Demo: Cross-System Proof

The demo shows three independent systems writing to the same ledger without knowing about each other:

```
TIME          SOURCE      TYPE                         AGENT_ID         DETAIL
10:00:00.500  kagenti     kagenti.agent.deployed       spiffe://demo    image: model-agent:v3
10:00:00.800  openshell   openshell.sandbox.created    sbx-demo-001     policy: github-readonly
10:00:01.200  kagenti     kagenti.tool.call            spiffe://demo    tool: check-model  trace: aaa
10:00:01.205  openshell   openshell.http_activity      sbx-demo-001     GET api.github.com  trace: aaa
10:00:02.100  kagenti     kagenti.tool.call            spiffe://demo    tool: promote-model  trace: bbb
10:00:02.105  openshell   openshell.network_activity   sbx-demo-001     DENY POST  trace: bbb
```

Three identity systems. Three event formats. Three independent hash chains. One verifiable timeline.

```bash
# Cross-system query by trace ID
python proof-explorer/proof.py query --correlation-id trace-aaa
# Returns entries from both OpenShell and Kagenti for the same request

# Verify all chains
python proof-explorer/proof.py verify --all
# 3 chains verified, 0 tampered

# Detect authorization gaps
python proof-explorer/proof.py drift --agent-id agt-demo-001
# "POST api.github.com denied by OpenShell but no governance scope evaluation found"
```

## Adapters

Thin bridges for existing agentic systems:

| Adapter | Source System | Input Format | Entry Type Namespace |
|---------|-------------|-------------|---------------------|
| `adapters/ocsf/` | NVIDIA OpenShell | OCSF v1.7.0 JSONL | `openshell.*` |
| `adapters/otel/` | Kagenti / any OTEL system | OTLP JSON spans | `kagenti.*` |
| `adapters/cpex/` | CPEX policy engine | OCSF 6003 audit events | `cpex.*` |
| `adapters/mlflow/` | MLflow Registry | Webhook + Plugin | `mlflow.*` |
| Direct gRPC | Any system | Any bytes | Your namespace |

## Architecture

```
System A ──→ adapter ──→ ┌─────────────────────┐
                         │  Immutable Ledger   │
System B ──→ adapter ──→ │  (gRPC :19292)      │ ←── proof-explorer CLI
                         │                     │
System C ──→ direct  ──→ │  PostgreSQL (chains)│
                         └─────────────────────┘
```

Each adapter is 100-150 lines of Python. Direct gRPC integration is ~30 lines. The ledger doesn't interpret event content — it chains raw bytes and makes them queryable by metadata.

## Scaling Roadmap

1. ~~**Pool PostgreSQL connections.**~~ **Done.** `deadpool-postgres` (configurable via `ARE_LEDGER_POOL_MAX_SIZE`, default 16). SHA-256-derived 64-bit advisory lock keys replace SQL `hashtext` (was int4, risked false serialization). Measured: single-chain at 100 req/s went from 738 errors / 11 req/s to 0 errors / 88 req/s, p99 from 220ms to 8.1ms.
2. ~~**Measure the bottlenecks.**~~ **Done.** Prometheus histograms for write duration, verification duration, and chain integrity retries. CPEX-shaped latency bench at `scripts/perf/cpex-latency-bench.py`.
3. ~~**Bounded chain verification.**~~ **Done.** `VerifyChain` walks chains in batches of 500 entries (bounded memory). `VerifyEntry` fetches only the predecessor instead of the full chain. No risk of OOM on long chains.
4. **Partition ledger storage.** Partition `ledger_entries` by time, tenant, or chain namespace once volume grows, and keep indexes aligned to `entry_type`, `agent_id`, `source_id`, `correlation_id`, and `written_ts` queries.
5. **Add verification checkpoints.** Periodically persist signed/checkpointed chain tips or Merkle roots so long-chain verification can resume from known-good anchors instead of replaying from genesis every time.
6. **Separate large payloads when needed.** Keep small event content inline; for large payloads, store a content hash in the ledger and move raw bytes to object storage.
7. **Define synthetic scale gates.** Run local smoke, hot-chain stress, multi-chain stress, query/read stress, restart/recovery, and long-soak drills, then publish their outputs alongside the evidence matrix.

## Project Structure

```
proto/                     The universal contract (9 RPCs)
src/                       Ledger server (Rust, gRPC, PostgreSQL)
migrations/                Database schema (append-only constraints + hash index)
contracts/                 Integration contracts (fleet ecosystem proof boundary)
sdks/python/               Python client SDK (WriteEntry, IssueReceipt, VerifyProof, GetEntryByHash)
adapters/ocsf/             OpenShell OCSF event bridge
adapters/otel/             Kagenti/OTEL span bridge
adapters/cpex/             CPEX audit seam consumer with gap detection and writer signatures
adapters/mlflow/             MLflow registry webhook listener + artifact/registry wrappers
proof-explorer/            Query, verify, timeline, and drift CLI
api/                       REST gateway for frontend (FastAPI + uvicorn)
frontend/                  7-act narrative proof explorer (React + Vite + motion)
demo/                      Self-contained demo with compose (includes joint CPEX/AuthBridge scenarios)
scripts/perf/              Latency benchmarks (k6 + Python harness)
tests/                     Evidence matrix and 146 automated checks
```

## Why This Exists

Every agentic platform logs events. None of them provide cross-system, cryptographically verifiable proof chains. The gap matters because:

- **Compliance** (EU AI Act August 2026, NIST AI RMF) requires auditable, tamper-evident decision records for autonomous systems.
- **Cross-system correlation** is impossible when OpenShell logs to JSONL, Kagenti logs to OTEL, and governance systems log to their own databases.
- **Observability is not proof.** Logs can be edited. Traces can be deleted. Hash-chained entries with independent verification are tamper-evident.

This ledger is the missing persistence and verification layer underneath protocol standards (MCP), runtime sandboxes (OpenShell), orchestration platforms (Kagenti), and per-framework governance (AGT).

## Origin

Open-sourced as standalone neutral infrastructure for the agentic ecosystem.

## License

Apache License 2.0. See [LICENSE](LICENSE).

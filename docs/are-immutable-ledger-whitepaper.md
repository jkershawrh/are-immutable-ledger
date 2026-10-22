# Tamper-Evident Evidence Infrastructure for Agentic AI Systems

**Author:** Jonathan Kershaw | **Date:** 2026-08-13 | **Version:** Draft 0.1

## Executive Summary

Agentic AI systems are proliferating across enterprise environments. Multiple orchestrators, sandboxes, model runtimes, and governance layers now operate concurrently, each producing its own event stream in its own format. Compliance frameworks (EU AI Act, effective August 2026; NIST AI RMF) require auditable, tamper-evident decision records for autonomous systems. Existing observability infrastructure, built on mutable logs and traces, cannot satisfy this requirement. Logs can be edited. Traces can be deleted. Neither provides a cross-system, cryptographically verifiable proof chain.

The ARE Immutable Ledger is a Rust-based, append-only evidence server that addresses this gap. It provides SHA-256 hash-chained entry storage with independent per-source chains, portable proof receipts for decentralized enforcement, and cross-system event correlation, all without imposing a shared identity system or event format. Written in approximately 2,900 lines of Rust (excluding tests) with `#![forbid(unsafe_code)]` at the crate root, the ledger exposes a 9-RPC gRPC contract backed by PostgreSQL. It has been validated against 146 automated checks across 15 evidence categories, including adversarial red-team scenarios, with zero failures recorded.

This paper describes the problem the ledger solves, its architecture and cryptographic design, the evidence collected during development, and the deployment model. It also identifies the material gaps that remain before enterprise governance use.

## Problem Statement

### The Observability Gap

Every major agentic platform produces event data. NVIDIA OpenShell logs sandbox activity as OCSF JSONL. Kagenti (Red Hat) exports orchestration telemetry as OTLP JSON spans. Governance systems like AuthBridge and CPEX record policy decisions in their own databases. Each system has its own log format, its own retention policy, and its own storage backend.

This creates three problems that standard observability tools cannot solve:

1. **Cross-system correlation is impossible.** When a model agent requests a tool call in Kagenti, and the OpenShell sandbox proxies that call to an external API, and a governance layer evaluates a policy gate, those three events exist in three separate log stores. Reconstructing the causal chain requires manual log aggregation, format normalization, and timestamp alignment. No cryptographic linkage binds the entries together.

2. **Tamper evidence does not exist.** Standard log stores (Elasticsearch, CloudWatch, Loki) provide search and retention, not integrity guarantees. An operator with database access can modify or delete entries without detection. For compliance purposes, the absence of tampering is indistinguishable from undetected tampering.

3. **Redundant enforcement multiplies latency.** In multi-hop agentic architectures, each service independently re-runs guardrail checks (PII scanning, policy evaluation, content filtering) because there is no verifiable, portable evidence that a previous hop already completed the check. This duplication adds latency and cost without improving security.

### Why Existing Approaches Fall Short

Blockchain-based approaches (Hyperledger, Ethereum L2) introduce consensus overhead, tokenomics complexity, and operational burden disproportionate to the actual requirement: proving that stored assertions were not modified after acceptance. Centralized audit databases lack cryptographic chaining and depend entirely on access controls for integrity. Certificate transparency logs solve a narrower problem (certificate issuance) and do not provide general-purpose event correlation.

The gap is specific: agentic systems need a lightweight, identity-neutral evidence plane that chains events per source, supports cross-system queries by shared identifiers, and provides portable proof receipts that downstream services can verify against their own trust policies.

## Architecture

### Design Principles

The ledger is built on four principles:

- **Identity neutrality.** The ledger does not maintain a user registry, resolve keys, or validate signatures. Writers use whatever identity format their system provides (SPIFFE SVIDs, agent UUIDs, sandbox identifiers). The ledger stores these as opaque metadata.

- **Format neutrality.** Event content is stored as opaque bytes. The ledger does not interpret, validate, or transform payloads. Producers own their schemas.

- **Per-source chain independence.** Each `entry_type` forms its own SHA-256 hash chain. Writes to different chains run in parallel. Verification is per-chain, so one corrupted chain does not invalidate others.

- **Proof without authority.** The ledger proves that a stored assertion was accepted and has not been modified. It does not prove that the assertion is true, that the writer was authorized, or that the claimed action actually occurred. Those determinations belong to the consumer's trust policy.

### System Overview

The ledger runs as a single binary that starts three concurrent servers:

```
                                    +-----------------------+
System A ---> adapter ------------> |  gRPC Server (:9092)  |
                                    |  (Tonic + Axum)       |
System B ---> adapter ------------> |                       |
                                    |  PostgreSQL           |
System C ---> direct gRPC --------> |  (deadpool-postgres)  |
                                    +-----------------------+
                                    |  Health Server (:8080)|
                                    |  /healthz /readyz     |
                                    |  /verifyz /shutdownz  |
                                    +-----------------------+
                                    |  Metrics Server(:8083)|
                                    |  /metrics (Prometheus)|
                                    +-----------------------+
```

The gRPC server handles all write, read, verification, and receipt operations through the `are.ledger.v1.ImmutableLedgerService` contract defined in `proto/immutable_ledger.proto`. The health server provides liveness (`/healthz`), readiness (`/readyz` with database and chain verification checks), detailed verification status (`/verifyz` as JSON), and an optional authenticated shutdown endpoint (`/shutdownz`). The metrics server exports Prometheus counters and histograms for write throughput, verification latency, chain integrity retries, and outbox delivery failures.

### Layered Rust Implementation

The server is structured in four layers, each defined as a separate module:

**gRPC Layer** (`src/grpc/mod.rs`, 547 lines). Tonic service implementation that maps protobuf request/response types to the service layer. Supports optional bearer-token authentication via a gRPC interceptor with constant-time token comparison to prevent timing side channels.

**Service Layer** (`src/service/mod.rs`, 2,007 lines including tests). Generic over `LedgerRepository` and `EventPublisher` traits. Implements chain tip lookup, write-with-retry using exponential backoff (10ms base, up to 10 configurable attempts), chain halt with timed auto-recovery (default 60 seconds), idempotency enforcement (all bound fields compared, including proof material), proof receipt issuance and verification, and batched chain verification (500 entries per batch for bounded memory).

**Repository Layer** (`src/repository/`, 1,103 lines). `LedgerRepository` trait with two implementations: `PostgresLedgerRepository` (production, using `deadpool-postgres` with configurable pool size and per-`entry_type` advisory locks) and `InMemoryLedgerRepository` (testing). The repository layer implements the transactional outbox pattern: each write atomically inserts both the ledger entry and an outbox record, ensuring event delivery is at-least-once without distributed transactions.

**Crypto Module** (`src/crypto/mod.rs`, 298 lines). SHA-256 hashing with a versioned canonical entry hash format. The module supports two hash versions (V2 and V3), dispatched by the `hash_version` field on each entry. Unknown versions fail closed (return `None`), preventing verification bypass through version injection.

### The gRPC Contract

The `ImmutableLedgerService` exposes 9 RPCs organized into three groups:

**Write and Receipt RPCs:**
- `WriteEntry` accepts an entry with metadata and opaque content bytes, chains it to the appropriate `entry_type` chain, and returns the entry ID, hash, chain position, timestamp, and hash version.
- `IssueReceipt` performs a write and returns the persisted proof material as a `ProofReceipt`, suitable for attachment to downstream requests.

**Lookup and Query RPCs:**
- `GetEntry` retrieves a single entry by UUID.
- `GetEntryByHash` retrieves an entry by its hash and entry type.
- `QueryEntries` supports filtering by `agent_id`, `correlation_id`, `source_id`, `entry_type` prefix, and time range, with cursor-based pagination (page size capped at 1,000).
- `GetChainTip` returns the latest entry for a given entry type.

**Verification RPCs:**
- `VerifyEntry` recomputes the canonical hash for a single entry and checks chain linkage to its predecessor.
- `VerifyProof` validates a proof receipt by looking up the entry by hash and type, then recomputing its canonical hash.
- `VerifyChain` walks an entire chain (or a bounded range) in batches of 500, verifying both hash integrity and chain linkage at each step.

### Database Schema

The ledger uses PostgreSQL with three tables in the `are_ledger` schema, defined across 8 SQL migrations:

**`ledger_entries`**: The append-only event store. Contains the entry UUID, entry type, agent ID, content bytes (up to 1 MiB), content type, source ID, optional correlation ID, optional idempotency key, entry hash, previous hash, chain position, timestamp, hash version, and optional proof material fields (writer signature, signer key reference, attestation report). A unique index on `(entry_type, chain_position)` enforces ordering. A partial unique index on `(entry_type, idempotency_key)` prevents duplicate writes. Additional indexes support queries by agent ID, source ID, correlation ID, entry type, and timestamp. Database-level permissions enforce immutability: the application role has INSERT and SELECT but not UPDATE or DELETE. The server verifies this constraint at startup and refuses to start if the role has mutation permissions.

**`ledger_chain_tips`**: A denormalized cache of the latest entry per chain. Indexed by entry type, storing the last entry ID, hash, position, and timestamp.

**`ledger_write_outbox`**: A transactional outbox for event delivery. Each write atomically creates a PENDING outbox record. A background processor polls for pending records and delivers them via HTTP with idempotency headers, exponential backoff, and permanent failure marking after configurable maximum retries (default 10).

### Cryptographic Design

#### Hash Chaining

Each entry's hash is computed from a canonical byte sequence using SHA-256. The canonical format uses length-delimited fields to prevent ambiguity:

```
field_name:byte_length:field_bytes\n
```

For example, an `entry_type` field with value "kagenti.tool.call" serializes as `entry_type:17:kagenti.tool.call\n`. This encoding prevents delimiter collision and ensures deterministic serialization regardless of field ordering or optional field presence.

The V3 canonical hash commits to 15 fields: hash version, entry ID, entry type, agent ID, content bytes, content type, source ID, correlation ID, idempotency key, input hash, writer signature (opaque bytes), signer key reference, attestation report (opaque bytes), chain position, timestamp (Unix milliseconds), and previous hash.

The V2 format (used for historical entries written before the V3 migration) commits to the same fields except writer signature, signer key reference, and attestation report. Both versions remain verifiable. The `hash_version` column, introduced in migration 006, labels each row with its hash format. A PostgreSQL CHECK constraint restricts the column to `ARE_LEDGER_ENTRY_HASH_V2` and `ARE_LEDGER_ENTRY_HASH_V3`, and the verification functions dispatch accordingly.

#### Advisory Lock Serialization

Writes to the same `entry_type` chain must be serialized to maintain the hash chain. The ledger derives a 64-bit PostgreSQL advisory lock key from the SHA-256 hash of the entry type string (taking the first 8 bytes as a big-endian i64). This replaced an earlier approach using PostgreSQL's built-in `hashtext` function (which produced 32-bit keys with higher collision probability). Different entry types acquire different advisory locks and write in parallel across separate database connections from the pool.

#### Three Layers of Proof

The ledger supports three optional, composable proof layers:

```
Layer 1: entry_hash           --> stored envelope not modified (ledger verifies)
Layer 2: writer_signature     --> writer-supplied identity evidence (consumer verifies)
         signer_key_reference --> which key to resolve
Layer 3: attestation_report   --> runtime/hardware evidence (consumer verifies)
```

All three are optional and identity-neutral. The ledger stores opaque bytes for Ed25519, ECDSA, SPIFFE SVIDs, SGX quotes, SEV-SNP reports, RATS EAT tokens, or any format the writer uses. V3 binds all three into the canonical hash. The ledger never interprets, resolves, or validates these fields. Consumers bear full responsibility for signature verification, key resolution, attestation appraisal, and trust policy enforcement.

### Adapter Architecture

Three adapter implementations bridge existing agentic systems to the ledger:

**OCSF Adapter** (`adapters/ocsf/ocsf_to_ledger.py`, 134 lines). Reads NVIDIA OpenShell OCSF v1.7.0 JSONL from stdin or file. Maps `class_uid` values to `entry_type` (e.g., 4001 maps to `openshell.network_activity`, 4002 maps to `openshell.http_activity`). Extracts `metadata.uid` as `agent_id` and `unmapped.request_id` as `correlation_id`. Preserves raw OCSF JSON as content bytes.

**OTEL Adapter** (`adapters/otel/otel_to_ledger.py`, 165 lines). Reads Kagenti/OTEL OTLP JSON spans. Maps span names to entry types under the `kagenti.*` namespace. Extracts `resource.attributes.service.name` as `agent_id` and `traceId` as `correlation_id`.

**MLflow Adapter** (`adapters/mlflow/`, 527 lines across 4 files). A webhook listener that receives MLflow model registry events, plus artifact and registry wrapper scripts. Writes events under the `mlflow.*` namespace.

All adapters use the Python gRPC client SDK (`sdks/python/`). Direct gRPC integration from any language requires approximately 30 lines of code.

### Proof Receipt Propagation

Receipts solve the redundant-enforcement problem in multi-hop agentic architectures. When an enforcement point (e.g., AuthBridge) runs a guardrail check:

1. AuthBridge calls `IssueReceipt` with the check result as content.
2. The ledger writes the entry, chains it, and returns a `ProofReceipt` containing the entry hash, chain position, and timestamp.
3. AuthBridge attaches the receipt to the forwarded request as a header: `X-Proof-Receipt: base64({"h":"<hash>","t":"<entry_type>"})`.
4. The next hop (e.g., MCP Gateway) calls `VerifyProof(entry_hash, entry_type)`.
5. If the ledger confirms the hash is valid, the consumer applies its local receipt policy: issuer verification, signature validation, freshness check, payload binding, check/policy version, audience, and purpose. Only if all requirements pass does it skip the redundant check.

Receipts are explicitly not credentials. They prove that the ledger accepted a particular writer assertion. They do not independently prove the assertion is true, the check actually ran, the implementation was sound, the result is current, or the writer was honest. The README, contract documentation, and UI all maintain this distinction.

## Evidence and Benchmarks

### Test Coverage

The repository maintains a 102-item evidence matrix (`tests/EVIDENCE_MATRIX.md`) spanning 15 categories. The automated evidence runner (`tests/run_evidence.py`) records results to `tests/evidence-results.json`. The latest snapshot reports **146 automated checks, all GREEN**. Ten matrix items remain YELLOW because they cover CLI behavior and manual/design-level verification not yet automated in the evidence runner.

**Evidence categories and automated check counts:**

| Category | Checks | Scope |
|---|---|---|
| L1: Ledger Core | 11 | Append-only enforcement, hash determinism, chain linkage, idempotency, DB permissions |
| L2: Chain Verification | 7 | Tamper detection, chain integrity, count accuracy, empty chains |
| L3: Cross-System Query | 7 | All filters, pagination, concurrent safety |
| L4: Identity Independence | 4 | Three ID formats, isolation, cross-identity correlation |
| L5: OCSF Adapter | 9 | Field mapping, content preservation, error handling |
| L6: OTEL Adapter | 8 | Field mapping, envelope parsing, error handling |
| L8: Demo Narrative | 6 | Cross-system correlation, drift detection |
| L9: Live Integration | 5 | Real OpenShell OCSF events, Kagenti OTEL spans |
| L10: Resilience | 5 | Concurrent stress (200 writes), restart survival, content limits |
| L11: Security | 10 | SQL injection, null bytes, unicode, field validation, data leakage |
| L12: Adversarial | 8 | Write flood (1000), query flood, payload flood, forgery, deletion |
| L13: Kagenti Live | 5 | OTEL collector health, agent traces, traceId preservation |
| L14: Synthetic | 4 | Multi-system lifecycle, concurrent agents, long chains |
| L15: Cross-System | 5 | Both sources coexist, trace ID joins, timeline interleaving |

Additional security testing categories (documented in `tests/SECURITY_TESTING.md`) cover proof receipt red-teaming (L16-L18, 28 checks), CPEX contract scenarios (L19, 11 checks), signature and attestation testing (L20-L21, 15 checks), totaling over 200 documented test scenarios across the full suite.

### Performance Benchmarks

Benchmarked on Podman-hosted PostgreSQL 16 (single node, no tuning) using CPEX-shaped workloads via the REST API gateway (`scripts/perf/cpex-latency-bench.py`):

| Scenario | p50 | p99 | Throughput | Errors |
|---|---|---|---|---|
| IssueReceipt (4 parallel chains, 100 req/s) | 4.4ms | 57.6ms | 87/s | 0 |
| IssueReceipt (single chain, 100 req/s) | 4.2ms | 8.1ms | 88/s | 0 |
| VerifyProof (under write load, 100 req/s) | 2.8ms | 6.6ms | N/A | 0 |
| Receipt round-trip (Issue + Verify, 50 req/s) | 8.0ms | 13.0ms | N/A | 0 |

Raw gRPC numbers (no REST gateway overhead): WriteEntry p50=1.7ms, p99=4.3ms at approximately 520 writes/second. VerifyProof p50=0.6ms, p99=1.7ms at approximately 1,400 verifications/second.

The connection pool improvement (replacing a global Mutex with `deadpool-postgres`) produced a measurable improvement on single-chain writes under load: from 738 errors and 11 req/s throughput with p99=220ms, to 0 errors and 88 req/s throughput with p99=8.1ms.

### Red-Team Results

The security testing suite covers 8 adversarial scenarios with confirmed results:

- **SQL injection** via `entry_type` and `agent_id` fields containing `'; DROP TABLE`: input stored literally, parameterized queries prevent execution.
- **Write flood** (1,000 writes across 10 chains, 10 concurrent threads): 900+ writes succeed, all chains valid.
- **Large payload flood** (50 concurrent writes at 500KB each, ~25MB burst): 40+ writes succeed, no OOM.
- **Forged entry** (direct INSERT with fabricated hash): row accepted by INSERT but `VerifyChain` detects the forged hash.
- **Entry deletion** (DELETE of mid-chain entry using DB owner role): `VerifyChain` detects the gap.
- **Replay attack** (duplicate INSERT with same chain position): database unique constraint rejects.
- **Chain tip tampering** (UPDATE to `ledger_chain_tips` cache): service recovers because it reads the tip from `ledger_entries`.
- **Cross-chain contamination** (write to chain A, verify chain B): chains are fully independent with no leakage.

Proof receipt red-teaming confirmed that forged hashes return NOT_FOUND, cross-type hash reuse returns NOT_FOUND, content/agent/correlation swaps cause hash verification failure, and idempotency key reuse with different proof material returns ALREADY_EXISTS.

## Deployment

### Container Deployment

The project includes a multi-stage Dockerfile based on `rust:1.90-bookworm`. The builder stage compiles the release binary with the vendored protobuf compiler. The runtime image is `debian:bookworm-slim` with only `ca-certificates` and `curl` installed. The binary exposes three ports: 9092 (gRPC), 8080 (health/readiness), and 8083 (Prometheus metrics).

```bash
# Local development with Docker Compose
cd demo
make up        # Starts ledger + PostgreSQL 16
make smoke     # Write sample entries and verify chains
make demo      # Full cross-system demo with OpenShell + Kagenti
```

### Configuration

All configuration is via environment variables (no config files):

| Variable | Default | Purpose |
|---|---|---|
| `ARE_LEDGER_DB_CONNECTION_STRING` | (required) | PostgreSQL connection string (supports `sslmode=require`) |
| `ARE_LEDGER_GRPC_PORT` | 9092 | gRPC server listen port |
| `ARE_LEDGER_HEALTH_PORT` | 8080 | Health/readiness HTTP port |
| `ARE_LEDGER_METRICS_PORT` | 8083 | Prometheus metrics HTTP port |
| `ARE_LEDGER_POOL_MAX_SIZE` | 16 | Connection pool max size |
| `ARE_LEDGER_CHAIN_MAX_RETRIES` | 10 | Write retry attempts before chain halt |
| `ARE_LEDGER_CHAIN_HALT_RECOVERY_SECONDS` | 60 | Auto-recovery timeout for halted chains |
| `ARE_LEDGER_VERIFY_INTERVAL_SECONDS` | 300 | Background chain verification interval (0 = disabled) |
| `ARE_LEDGER_MAX_CONTENT_SIZE_BYTES` | 1048576 | Maximum entry content size (1 MiB) |
| `ARE_LEDGER_API_TOKEN` | (unset) | Bearer token for gRPC auth (disabled when unset) |
| `ARE_LEDGER_SHUTDOWN_TOKEN` | (unset) | Bearer token for /shutdownz (hidden when unset) |
| `ARE_LEDGER_OUTBOX_HTTP_ENDPOINT` | (unset) | HTTP endpoint for outbox event delivery |
| `ARE_LEDGER_OUTBOX_MAX_RETRIES` | 10 | Max publish attempts before permanent failure |

### Security Considerations

For shared deployments, operators should:

- Set `sslmode=require` or `sslmode=verify-full` in the database connection string for encrypted PostgreSQL connections (using rustls, no OpenSSL dependency).
- Place the gRPC listener behind TLS/mTLS-capable infrastructure and set `ARE_LEDGER_API_TOKEN`.
- If using the REST gateway, set `GATEWAY_API_TOKEN`, bind to `127.0.0.1`, and keep it behind TLS infrastructure.
- Ensure the PostgreSQL application role has INSERT and SELECT on `are_ledger.ledger_entries` but not UPDATE or DELETE. The server verifies this at startup.

### Observability

The Prometheus metrics endpoint exposes:

- `are_ledger_write_total` (counter, labeled by outcome: ok/invalid/error)
- `are_ledger_write_duration_seconds` (histogram, buckets from 1ms to 1s)
- `are_ledger_verify_duration_seconds` (histogram, buckets from 0.5ms to 100ms)
- `are_ledger_chain_integrity_retries` (histogram, 0 to 10 attempts)
- `are_ledger_chain_verify_failure_total` (counter, invalid link or hash detected)
- `are_outbox_publish_failure_total` (counter, HTTP publish failures)
- `are_ledger_chain_integrity_valid` (gauge, 1 = all chains valid, 0 = failure detected)

A background verifier (configurable interval, default 5 minutes) walks all chains, updates the Prometheus gauge, and enriches the `/readyz` endpoint so that chain verification failures make the service report as not ready.

### Frontend

The repository includes a React/Vite/TypeScript proof explorer UI (`frontend/`). Built with `@xyflow/react` for canvas-based graph rendering and Zustand for state management, it provides a visual interface for browsing chains, verifying entries, and exploring cross-system correlations through the REST gateway.

## Known Limitations and Enterprise Gaps

The `docs/oss-boundary-and-hardening-status.md` document in the repository defines what the ledger can and cannot establish, along with 12 material gaps that remain before enterprise governance use. The most significant are summarized here:

1. **Writer authentication and authorization.** The optional bearer token is deployment-wide. There is no per-tenant authorization, writer-to-namespace policy, or administrative RBAC.

2. **Signature semantics.** V3 binds opaque signature bytes into the hash, but no canonical signed-payload contract, algorithm policy, key resolution, certificate path validation, or rotation behavior is defined.

3. **External anchoring.** A database administrator can replace history and recompute a chain. There are no signed checkpoints, transparency-log witnesses, or external anchors to prevent split-view attacks.

4. **Archival and recovery.** Checkpointed export, WORM manifests, online-to-archive verification, and disaster-recovery drills are not implemented. The `docs/retention-and-archival.md` document explains why raw TTL deletion is unsafe and outlines a 7-step archival protocol that must be implemented before entries can be safely removed.

5. **Privacy lifecycle.** Immutable payloads can conflict with GDPR minimization, correction, and erasure requirements. Sensitive content should remain outside the ledger; producers should record a digest and controlled reference only.

6. **Single-instance availability.** The reference deployment uses a single PostgreSQL instance. HA topology, partitioning, admission control, and noisy-neighbor isolation need production design work.

The recommended enterprise composition treats the ledger as the evidence plane beneath separate services for identity/authentication, policy/authorization, governance workflow, knowledge/memory projections, receipt trust-policy evaluation, signed checkpointing, and privacy/records controls.

## Conclusion

The ARE Immutable Ledger provides a focused, well-tested primitive for agentic AI governance: tamper-evident, hash-chained evidence storage with identity-neutral, format-neutral design. Its 9-RPC gRPC contract, per-source chain independence, and portable proof receipts address the specific gap between existing observability infrastructure and the cryptographic audit trail that emerging compliance frameworks demand.

The project is at version 0.1.0. The core evidence surface (append-only storage, hash chaining, chain verification, proof receipts, cross-system correlation, and adapter bridges for OpenShell, Kagenti, and MLflow) is functional and validated against 146 automated checks with zero failures. Performance on untuned single-node PostgreSQL shows sub-5ms p50 write latency at the gRPC layer and sub-1ms p50 verification latency.

The next phase of work focuses on the enterprise gaps identified above: writer authentication and RBAC, signed chain checkpoints for external anchoring, archival-safe chain compaction, and HA deployment patterns. The scaling roadmap (connection pool and bounded verification are complete; partitioning, verification checkpoints, and synthetic scale gates remain) provides a clear path from the current single-node reference deployment toward production-grade operation.

The repository is open-sourced under the Apache License 2.0.

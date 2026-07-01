# Immutable Ledger for Agentic Systems

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

A universal, cryptographically verifiable audit ledger for autonomous AI agents. Any agentic system writes events with its own identity and format. The ledger chains them, stores them, and makes them independently verifiable.

> **The agentic ecosystem has protocols (MCP), runtimes (OpenShell, Goose), orchestration (Kagenti), and per-framework governance (AGT). What it doesn't have is a shared, neutral, cross-system proof chain. This is that layer.**

## What It Does

The ledger answers three questions for any agentic system:

1. **What happened?** Append-only event storage with per-source hash chains.
2. **Can you prove it?** SHA-256 hash chaining with cryptographic chain verification.
3. **Can you correlate across systems?** Query by agent ID, correlation ID, source, time range, or entry type across independent writers.

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
- **V2 canonical proof envelope** - hashes commit to entry ID, metadata, content, idempotency key, chain position, timestamp, and previous hash using length-delimited fields.
- **Concurrent-safe** - PostgreSQL advisory locks serialize writes per chain. Integrity violations trigger circuit breaker after 5 retries.
- **Idempotent** - optional idempotency keys prevent duplicate entries on retry; reusing a key with different content or metadata returns a conflict.
- **Cross-system queries** - `QueryEntries` filters by agent_id, correlation_id, source_id, entry_type prefix, and time range. One query returns entries from all sources for the same agent or request.
- **Hardened admin surface** - `/shutdownz` is disabled unless `ARE_LEDGER_SHUTDOWN_TOKEN` is set and requires a bearer token when enabled. gRPC bearer-token auth can be enabled with `ARE_LEDGER_API_TOKEN`.
- **Proof receipts** - `IssueReceipt` writes an entry and returns a compact `ProofReceipt` (hash, type, position, timestamp). `VerifyProof` validates a receipt by hash without knowing the entry ID. Receipts travel as HTTP headers so downstream services verify a check ran without re-executing it.

## Proof Receipts

Receipts solve the redundant-check problem in multi-hop agentic architectures. When AuthBridge runs a guardrail, it issues a receipt. The MCP Gateway verifies the receipt and skips the same guardrail. The MCP Server does the same.

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
  → Skips re-running the guardrail
```

Receipts are NOT credentials — they prove a check ran, they don't grant authority. The V2 hash commits to all entry fields (content, agent_id, correlation_id, entry_id, chain_position, timestamp, previous_hash). Changing any field breaks verification.

## Performance

Benchmarked on Podman-hosted PostgreSQL (single node, no tuning):

| Operation | p50 | p95 | p99 | Throughput |
|---|---|---|---|---|
| WriteEntry | 1.7ms | 2.9ms | 4.3ms | ~520/sec |
| IssueReceipt | 2.9ms | 7.2ms | 13.9ms | ~280/sec |
| VerifyProof | 0.6ms | 1.3ms | 1.7ms | ~1,400/sec |
| VerifyProof (under write load) | 0.9ms | — | 1.9ms | — |
| GetChainTip (200-entry chain) | 0.4ms | — | 0.6ms | — |

### Known Scale Considerations

| Concern | Current behavior | Mitigation path |
|---|---|---|
| **Advisory lock contention** | Writes to the same `entry_type` serialize via PostgreSQL advisory locks. 5 concurrent writers to ONE chain: ~200 writes/sec with errors. | Use distinct `entry_type` per source. Parallel chains scale linearly — 5 chains = 5x throughput. |
| **Single PostgreSQL instance** | All reads and writes go through one database connection. | Read replicas for VerifyProof. Connection pooling (PgBouncer). Horizontal partitioning by entry_type prefix. |
| **Chain verification on long chains** | VerifyChain reads all entries for an entry_type. 200-entry chain: fine. 1M entries: full table scan. | Add chain verification checkpoints. Verify only the last N entries from a known-good checkpoint. |
| **Storage growth** | Each entry stores full content bytes (up to 1 MiB). High-volume systems generate significant storage. | Content compression. Content-addressed storage (store hash, external blob). TTL-based archival. |
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

- `tests/EVIDENCE_MATRIX.md` summarizes automated, live, and not-yet-automated coverage.
- `tests/evidence-results.json` records the latest evidence runner output.
- `tests/SECURITY_TESTING.md` documents red-team and hardening checks.
- `proof-explorer/proof.py verify --all` independently verifies stored chains through the public API.

Useful local verification commands:

```bash
cargo test --all --locked
cargo clippy --all-targets --all-features --locked -- -D warnings
python tests/run_evidence.py
python proof-explorer/proof.py verify --all
```

The service exposes Prometheus metrics at `/metrics` on `ARE_LEDGER_METRICS_PORT`:

- `are_ledger_write_total`
- `are_ledger_chain_verify_failure_total`
- `are_outbox_publish_failure_total`

Hash compatibility note: this pre-release standalone ledger uses the V2 canonical proof envelope as its initial public contract. No production data has been written with the earlier experimental hash shape; if you have local demo data from before V2, reload it.

## Security Notes

For shared deployments, put the gRPC listener behind TLS/mTLS-capable infrastructure and set `ARE_LEDGER_API_TOKEN`; clients can pass the token explicitly or through the same environment variable. Set `ARE_LEDGER_SHUTDOWN_TOKEN` only for controlled graceful-shutdown drills, and call `/shutdownz` with `Authorization: Bearer <token>`.

## Demo: Cross-System Proof

The demo shows three independent systems writing to the same ledger without knowing about each other:

```
TIME          SOURCE      TYPE                         AGENT_ID         DETAIL
10:00:00.100  are         are.passport.issued          agt-demo-001     scope: model.promote:model/*
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
| Direct gRPC | Any system | Any bytes | Your namespace |

## Architecture

```
System A ──→ adapter ──→ ┌─────────────────────┐
                         │  Immutable Ledger    │
System B ──→ adapter ──→ │  (gRPC :19292)       │ ←── proof-explorer CLI
                         │                     │
System C ──→ direct  ──→ │  PostgreSQL (chains) │
                         └─────────────────────┘
```

Each adapter is 100-150 lines of Python. Direct gRPC integration is ~30 lines. The ledger doesn't interpret event content — it chains raw bytes and makes them queryable by metadata.

## Scaling Roadmap

The current implementation is intentionally small and correctness-first. A practical scale-up path is:

1. **Pool PostgreSQL connections.** Replace the single mutex-wrapped client with a connection pool while retaining per-`entry_type` advisory locks for chain serialization.
2. **Measure the bottlenecks.** Add histograms/counters for write latency, advisory-lock wait time, idempotency conflicts, chain-integrity retries, query latency, verification latency, and outbox age.
3. **Partition ledger storage.** Partition `ledger_entries` by time, tenant, or chain namespace once volume grows, and keep indexes aligned to `entry_type`, `agent_id`, `source_id`, `correlation_id`, and `written_ts` queries.
4. **Add verification checkpoints.** Periodically persist signed/checkpointed chain tips or Merkle roots so long-chain verification can resume from known-good anchors instead of replaying from genesis every time.
5. **Separate large payloads when needed.** Keep small event content inline; for large payloads, store a content hash in the ledger and move raw bytes to object storage.
6. **Define synthetic scale gates.** Run local smoke, hot-chain stress, multi-chain stress, query/read stress, restart/recovery, and long-soak drills, then publish their outputs alongside the evidence matrix.

## Project Structure

```
proto/                     The universal contract (10 RPCs)
src/                       Ledger server (Rust, gRPC, PostgreSQL)
migrations/                Database schema (append-only constraints + hash index)
sdks/python/               Python client SDK (WriteEntry, IssueReceipt, VerifyProof, GetEntryByHash)
adapters/ocsf/             OpenShell OCSF event bridge
adapters/otel/             Kagenti/OTEL span bridge
proof-explorer/            Query, verify, timeline, and drift CLI
api/                       REST gateway for frontend (Flask)
frontend/                  7-act narrative proof explorer (React + Vite + motion)
demo/                      Self-contained demo with compose
tests/                     Evidence matrix: 116 tests across 18 categories
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

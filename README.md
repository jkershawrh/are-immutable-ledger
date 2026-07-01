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
rpc WriteEntry(WriteEntryRequest) returns (WriteEntryResponse);

message WriteEntryRequest {
  string entry_type = 1;       // your namespace: "openshell.*", "kagenti.*", "myagent.*"
  string agent_id = 2;         // YOUR identity — sandbox ID, SPIFFE SVID, whatever you use
  bytes  content = 3;          // YOUR event format — OCSF, OTLP, JSON, protobuf
  string content_type = 4;     // "application/ocsf+json", "application/otlp+json", etc.
  string source_id = 5;        // your system name
  string correlation_id = 6;   // W3C trace-id, X-Request-ID, or any cross-system join key
  string idempotency_key = 7;  // safe retries
}
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

## Quick Start

```bash
cd demo
make up        # Start ledger + postgres
make smoke     # Write sample entries and verify chains
make demo      # Full cross-system demo with OpenShell + Kagenti
```

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
# "POST api.github.com denied by OpenShell but no ARE scope evaluation found"
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

## Project Structure

```
proto/                     The universal contract (immutable_ledger.proto)
src/                       Ledger server (Rust, gRPC, PostgreSQL)
migrations/                Database schema (append-only constraints)
sdks/python/               Python client SDK
adapters/ocsf/             OpenShell OCSF event bridge
adapters/otel/             Kagenti/OTEL span bridge
proof-explorer/            Query, verify, and timeline CLI
demo/                      Self-contained demo with compose
tests/                     Integration and gRPC contract tests
```

## Why This Exists

Every agentic platform logs events. None of them provide cross-system, cryptographically verifiable proof chains. The gap matters because:

- **Compliance** (EU AI Act August 2026, NIST AI RMF) requires auditable, tamper-evident decision records for autonomous systems.
- **Cross-system correlation** is impossible when OpenShell logs to JSONL, Kagenti logs to OTEL, and governance systems log to their own databases.
- **Observability is not proof.** Logs can be edited. Traces can be deleted. Hash-chained entries with independent verification are tamper-evident.

This ledger is the missing persistence and verification layer underneath protocol standards (MCP), runtime sandboxes (OpenShell), orchestration platforms (Kagenti), and per-framework governance (AGT).

## Origin

Extracted from the [ARE Foundation](https://github.com/srex-dev/are-foundation) project's S0 immutable ledger service. Open-sourced as standalone neutral infrastructure for the agentic ecosystem.

## License

Apache License 2.0. See [LICENSE](LICENSE).

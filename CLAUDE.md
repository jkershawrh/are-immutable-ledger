# are-immutable-ledger

Rust-based append-only cryptographic ledger server for agentic AI trust infrastructure. Provides SHA-256 hash-chained event storage with per-source chains, portable proof receipts for decentralized enforcement, and cross-system event correlation. Solves duplicated guardrails in multi-hop agentic architectures (AuthBridge, MCP Gateway, AI Gateway).

## Quick Start

```bash
# Build (requires protobuf compiler, vendored via protoc-bin-vendored)
cargo build --release

# Run via Docker Compose (recommended for local dev)
cd demo
make up        # Starts ledger + PostgreSQL 16
make smoke     # Write sample entries and verify chains
make demo      # Full cross-system demo

# Run standalone (requires PostgreSQL)
export ARE_LEDGER_DB_CONNECTION_STRING=...
cargo run --release
# Starts: gRPC (:9092), health (:8080), metrics (:8083)
```

## Testing

```bash
cargo test --all --locked                              # Rust unit + integration tests
cargo clippy --all-targets --all-features --locked -- -D warnings
cargo fmt --all --check
python tests/run_evidence.py                           # Evidence matrix (146 checks)
python proof-explorer/proof.py verify --all            # Independent chain verification
python -m pytest -q tests/test_gateway_contract.py     # gateway contract tests
bash scripts/release-test.sh                           # Full release checklist (requires containers)
```

CI: GitHub Actions runs `rust` (fmt, clippy, test) and `gateway` (Python pytest) jobs.

## File Structure

| Path | Purpose |
|------|---------|
| `proto/immutable_ledger.proto` | gRPC contract: 9 RPCs in are.ledger.v1 package |
| `src/main.rs` | Entry point: 3 Axum/Tonic servers (gRPC, health, metrics) |
| `src/config/` | AppConfig from ARE_LEDGER_* env vars |
| `src/crypto/` | SHA-256 hashing, V2 canonical entry hash, advisory lock keys |
| `src/db_permissions/` | Startup check: role has INSERT+SELECT but NOT UPDATE/DELETE |
| `src/grpc/` | Tonic gRPC service impl |
| `src/service/` | Business logic: validation, chain tips, retry, halt/recovery, proof receipts |
| `src/repository/` | LedgerRepository trait + Postgres (deadpool-postgres, advisory locks) and InMemory impls |
| `migrations/` | 8 SQL migrations |
| `api/gateway.py` | Async FastAPI REST gateway (proxies to gRPC via Python SDK), served by uvicorn. |
| `frontend/` | React + Vite + TypeScript proof explorer UI (@xyflow/react, zustand) |
| `sdks/python/` | Python gRPC client SDK |
| `adapters/ocsf/` | NVIDIA OCSF event bridge |
| `adapters/otel/` | Kagenti/OTEL span bridge |
| `proof-explorer/proof.py` | CLI: verify, query, timeline, drift analysis |
| `adapters/mlflow/` | MLflow webhook listener + artifact/registry wrappers |
| `src/tls.rs` | Optional rustls-based TLS for Postgres connections |
| `src/verifier.rs` | Background chain verification + health enrichment |
| `scripts/release-test.sh` | Full release test suite |
| `demo/` | Docker Compose + Makefile + demo scripts |

## Architecture

**Layered design:**
1. **gRPC layer** (src/grpc/) -- Tonic server, optional bearer-token auth via interceptor
2. **Service layer** (src/service/) -- Generic over `LedgerRepository` and `EventPublisher`. Chain tip lookup, retry with exponential backoff, chain halt/recovery, idempotency, proof receipt issue/verify, batch chain verification (500)
3. **Repository layer** (src/repository/) -- `PostgresLedgerRepository` (advisory locks, transactional outbox) and `InMemoryLedgerRepository` (for tests)
4. **Crypto module** (src/crypto/) -- V2 canonical entry hash with length-delimited fields

**Key patterns:**
- `#![forbid(unsafe_code)]` at crate root
- Per-entry-type independent hash chains; same-chain writes serialize via PostgreSQL advisory locks
- Outbox pattern for event publishing (transactional outbox table, background polling, HTTP delivery)
- Three proof layers: entry hash (ledger verifies), writer signature (downstream verifies), attestation report (hardware root)
- Protobuf compiled at build time via build.rs
- Structured JSON logging via tracing + tracing-subscriber
- Background chain verifier (configurable interval, `/verifyz` JSON endpoint, Prometheus gauge)
- Optional Postgres TLS via rustls (auto-detected from `sslmode` in connection string)

**Database:** PostgreSQL in `are_ledger` schema. Tables: `ledger_entries` (append-only), `ledger_chain_tips`, `ledger_write_outbox`. Startup verifies role lacks UPDATE/DELETE permissions.

**Default ports:** gRPC 9092 (demo: 19292), health 8080 (demo: 18080), metrics 8083 (demo: 18083), REST gateway 18099, MLflow webhook listener 18098.

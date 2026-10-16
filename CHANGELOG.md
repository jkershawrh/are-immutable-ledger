# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-10-16

### Added

- **Praxis PPE preview adapter** (`adapters/praxis_ppe/`): consumes
  producer-neutral `praxis.ppe.audit.v1` decisions, maps them to OCSF 6003,
  and requests ledger proof receipts. Entry namespace `praxis.ppe.*`,
  deliberately separate from the CPEX adapter's `cpex.*`. Contract defined in
  `contracts/praxis-ppe-ocsf-ledger-contract.md`.
- **`demo/praxis-audit/`** — the joint demo on the real Praxis pipeline: an
  HR copilot making MCP tool calls through a Praxis gateway (Keycloak
  identity, PPE policy filter, session taint via Valkey), every decision
  landing in the ledger as a signed OCSF 6003 record. Includes tamper and
  deletion scenarios that fail loudly when detection is absent, a live chat
  walkthrough, a recorder, and offline verification with per-file hashes.
- **CPEX adapter AID-EMIT-1 alignment**: reads `aid.*` keys alongside legacy
  `cpex.*` records, orders `emission_seq` per epoch, and vendors the Rev 3
  evidence fixtures (real `plugin_panic` beat, one stream across two epochs).
- Regression tests for the JCS scalar rejection in `canonicalize_content`.

### Changed

- **The REST gateway is now async FastAPI served by uvicorn**, replacing the
  Flask implementation that accumulated threads under sustained write load
  (#11). The REST contract is unchanged: query filters, result caps and
  truncation markers, chain source classification, timeline cross-system
  links, `400` (not `422`) on malformed query parameters, and the
  `GATEWAY_HOST`/`GATEWAY_PORT` env contract all behave as before.
  Fail-closed auth without `GATEWAY_API_TOKEN` is preserved from #9, and
  `api/requirements.txt` moves from `flask`/`flask-cors` to
  `fastapi`/`uvicorn`.

### Fixed

- GapDetector checks the head of every epoch — a first record above 0 is a
  "GAP at head", so a restart that lost record 0 no longer passes
  `--strict-gaps` — and flags per-stream epoch regression (#15).
- Online chain verification is bounded; hash version migration is
  metadata-first.
- Outbox rows are skipped when publishing is disabled.
- `canonicalize_content` rejects floats, NaN and Infinity with path-qualified
  errors before hashing: RFC 8785 has no canonical encoding for them, and
  the value feeds the ledger `input_hash` (#16 review).
- The praxis-audit demo's `gateway.sh` verifies PID command lines before
  signalling, so a recycled or similarly named PID can no longer terminate an
  unrelated process; all demo compose ports are bound to `127.0.0.1`.

### Security

- rustls bumped to 0.23.46 (RUSTSEC-2026-0346..0349).
- async-trait bumped to 0.1.92 (also clears the Rust 1.99 `double_must_use`
  clippy gate that fires in the macro's generated code).
- Frontend lockfile refreshed for the `browserslist`, `source-map-js`, and
  `baseline-browser-mapping` advisories.
- CI now runs `cargo audit`, `pip-audit`, and `npm audit --audit-level=high`
  gates alongside fmt/clippy/test.

### Testing

- 61 Rust tests, 138 Python tests (gateway contract/auth, CPEX adapter,
  Praxis PPE adapter, MLflow webhook), 146-check evidence matrix.

## [0.1.0] — 2026-08-12

Initial release: append-only cryptographic ledger for agentic AI trust
infrastructure.

- 9 gRPC RPCs (WriteEntry, IssueReceipt, VerifyProof, VerifyChain,
  GetEntryByHash, QueryEntries, VerifyEntry, GetEntry, GetChainTip)
- V3 canonical hash envelope binding writer signatures and attestation
  reports into the entry hash
- PostgreSQL backend with advisory locks, connection pooling, and optional
  rustls-based TLS
- Background chain verifier (`/readyz`, `/verifyz`, Prometheus gauge)
- Outbox pattern with exponential backoff; DB permission enforcement
  (INSERT+SELECT only); constant-time bearer token comparison
- OCSF, OTEL, and MLflow adapters; REST gateway; proof-explorer CLI;
  React + Vite frontend; Python gRPC SDK; Docker Compose demo

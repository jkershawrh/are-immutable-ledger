# Security Testing & Red Team Evidence

## Testing Depth Summary

| Category | Tests | Coverage |
|---|---|---|
| L1: Ledger Core | 11 | Append-only enforcement, deterministic hashing, chain linkage, idempotency |
| L2: Chain Verification | 6 | Tamper detection, chain integrity, count accuracy, empty chains |
| L3: Cross-System Query | 7 | All filters, pagination, concurrent safety |
| L4: Identity Independence | 3 | Three ID formats, isolation, cross-identity correlation |
| L5: OCSF Adapter | 9 | Field mapping, content preservation, error handling |
| L6: OTEL Adapter | 8 | Field mapping, envelope parsing, error handling |
| L8: Demo Narrative | 6 | Cross-system correlation, drift detection |
| L9: Live Integration | 5 | Real OpenShell OCSF events, Kagenti OTEL spans, cross-system correlation |
| L10: Resilience | 5 | Concurrent stress, restart survival, content limits |
| **L11: Security** | **10** | **SQL injection, null bytes, unicode, field validation, DB permissions, data leakage** |
| **L12: Adversarial** | **8** | **Write flood, query flood, large payload flood, forged entries, deletion detection, replay attacks, cross-chain isolation** |
| **L13: Kagenti Live** | **5** | **OTEL collector health, agent traces captured, traceIds preserved, chains verified** |
| **L14: Synthetic** | **4** | **Multi-system lifecycle, concurrent agents, long chains, timeline reconstruction** |
| **L15: Cross-System** | **5** | **Both sources coexist, trace ID joins both, timeline interleaves, chains independent, drift detectable** |
| **L16: Proof Receipts** | **7** | **IssueReceipt, VerifyProof, round-trip encoding, chain of trust, cross-service verification** |
| **L17: Receipt Security** | **12** | **Forged hash, cross-type verify, replay staleness, content/agent/correlation swap, idempotency conflict, SQL injection, flood** |

## Attack Surface Coverage

### gRPC API (6 endpoints)

| Endpoint | Injection Tested | Abuse Tested | Auth |
|---|---|---|---|
| WriteEntry | L11.03, L11.04 (SQL), L11.05 (null), L11.06 (unicode), L11.07 (empty fields) | L12.01 (flood), L12.03 (large payload) | None (infrastructure-level) |
| GetEntry | Via L1.04 | — | None |
| QueryEntries | Via L3.01-L3.07 | L12.02 (query flood) | None |
| VerifyEntry | Via L2.01-L2.02 | — | None |
| VerifyChain | Via L2.03, L12.05, L12.06 | — | None |
| GetChainTip | Via L2.06 | — | None |

### Database Layer

| Attack | Test ID | Result |
|---|---|---|
| UPDATE on ledger_entries | L1.09 | BLOCKED (permission denied) |
| DELETE on ledger_entries | L1.10 | BLOCKED (permission denied) |
| Chain tip tampering | L11.01 | Service recovers — uses entries table for tip |
| Outbox corruption | L11.02 | Chain integrity unaffected |
| Direct INSERT with wrong hash | L11.09 | Accepted but VerifyEntry catches it |
| Forged entry in chain | L12.05 | VerifyChain detects |
| Entry deletion from chain | L12.06 | VerifyChain detects gap |
| Duplicate chain_position | L12.07 | DB unique constraint rejects |

### Cryptographic Integrity

| Property | Test ID | Method |
|---|---|---|
| Hash determinism | L1.06 | Recompute SHA-256 from fields, compare |
| Chain linkage | L1.07 | Verify entry N's previous_hash = entry N-1's hash |
| Genesis hash | L1.08 | First entry uses SHA-256("ARE_LEDGER_GENESIS") |
| Tamper detection | L2.02 | Modify content in DB, VerifyEntry catches |
| Hash tampering detection | L10.02 | Modify hash in DB, VerifyChain catches |

### Deployment Security

| Risk | Test ID | Status |
|---|---|---|
| Default credentials in compose | L12.10 | Documented — demo-only |
| Health endpoint data leakage | L11.08 | No credentials or hashes in response |
| Metrics endpoint data leakage | L11.10 | No entry content in metrics |
| SQL injection via string fields | L11.03, L11.04 | Parameterized queries — stored literally |

## Red Team Scenarios Tested

### 1. SQL Injection (L11.03, L11.04)
**Attack:** Inject SQL via `entry_type` and `agent_id` fields containing `'; DROP TABLE`.
**Result:** Input stored literally as data. Parameterized queries prevent execution. Table intact.

### 2. Write Flood / DoS (L12.01)
**Attack:** 1000 writes across 10 chains from 10 concurrent threads.
**Result:** 900+ writes succeed. All chains valid. Service remains healthy.

### 3. Large Payload Flood (L12.03)
**Attack:** 50 concurrent writes with 500KB content each (~25MB burst).
**Result:** 40+ writes succeed. DB handles burst without OOM.

### 4. Forged Entry (L12.05)
**Attack:** INSERT a row directly into the database with a fabricated hash.
**Result:** Row accepted (INSERT allowed) but `VerifyChain` detects the forged hash.

### 5. Entry Deletion (L12.06)
**Attack:** DELETE a mid-chain entry using the DB owner role.
**Result:** `VerifyChain` detects the gap — chain reports INVALID.

### 6. Replay Attack (L12.07)
**Attack:** INSERT a duplicate row with the same `chain_position` and `entry_type`.
**Result:** DB unique constraint rejects the duplicate.

### 7. Chain Tip Tampering (L11.01)
**Attack:** UPDATE `ledger_chain_tips` table to corrupt the cached tip hash.
**Result:** Service reads tip from the `ledger_entries` table (not the cache), so writes continue correctly.

### 8. Cross-Chain Contamination (L12.08)
**Attack:** Write entries to chain A, verify chain B is unaffected.
**Result:** Chains are fully independent — different hashes, different positions, no cross-contamination.

## Proof Receipt Red Team (L17)

Receipts introduce new attack surface — a portable proof token that downstream services trust. Every vector tested:

| Attack | What the attacker tries | Result | Test |
|---|---|---|---|
| **Forge a receipt** | Fabricate a hash that passes VerifyProof | NOT_FOUND — hash doesn't exist in ledger | L17.01 |
| **Cross-type theft** | Use a valid hash against a different entry_type | NOT_FOUND — hash is scoped to type | L17.02 |
| **Replay** | Reuse an old receipt on a new request | Verifies, but written_ts exposes staleness — downstream sets freshness threshold | L17.03 |
| **Content swap** | Change what the receipt claims was validated | Hash verification FAILS — content is committed in hash | L17.04 |
| **Issuer impersonation** | Change agent_id to claim a more trusted issuer | Hash verification FAILS — agent_id is committed in hash | L17.05 |
| **Request rebinding** | Change correlation_id to bind receipt to different request | Hash verification FAILS — correlation_id is committed in hash | L17.06 |
| **Idempotency abuse** | Reuse key with different content | ALREADY_EXISTS error — conflict detected | L17.08 |
| **SQL injection** | Inject SQL via entry_type in IssueReceipt | Stored literally, no execution | L17.11 |
| **Receipt flood** | Issue 100 receipts from 5 concurrent threads | All succeed, service healthy | L17.12 |

### What receipts DON'T protect against

| Limitation | Why | Mitigation |
|---|---|---|
| **Lying writer** | If AuthBridge writes "guardrail: clean" when it wasn't, the receipt faithfully proves the lie | Attestation is the writer's responsibility. Receipt proves the claim was made, not that it's true. |
| **Replay within freshness window** | A receipt issued 100ms ago is indistinguishable from a new one | Downstream services must bind receipt to the specific request (via correlation_id match) |
| **Receipt interception** | If an attacker reads the X-Proof-Receipt header, they know the hash | Hash is not a secret — knowing it only lets you verify, not forge. The entry_type scoping prevents cross-context use. |

## Documented Gaps (Honest Assessment)

These are known limitations, not bugs. They represent design decisions appropriate for the current stage:

| Gap | Why It Exists | Mitigation |
|---|---|---|
| **No authentication** | Ledger is neutral infrastructure — auth is the deployer's responsibility | Deploy behind mTLS, API gateway, or service mesh |
| **No encryption in transit** | Demo uses plaintext gRPC | Production deployment adds TLS |
| **No multi-tenant isolation** | Single-tenant design | Namespace entry_types per tenant |
| **No rate limiting** | Service-level rate limiting not implemented | Deploy behind API gateway with rate limits |
| **Static genesis hash** | SHA-256("ARE_LEDGER_GENESIS") is hardcoded | Configurable via `ARE_LEDGER_GENESIS_HASH_INPUT` env var |
| **Default credentials in demo** | Demo compose uses `ledger/ledger` | Production deploys with proper secrets management |
| **Advisory lock contention** | Concurrent writes to same chain serialize (~200/sec under contention) | Use distinct entry_types per source; parallel chains scale linearly |
| **Single DB instance** | All reads/writes through one connection | Read replicas for VerifyProof, connection pooling, partitioning |
| **No receipt expiry** | Receipts verify indefinitely as long as the entry exists | Downstream services enforce freshness via written_ts check |
| **Receipts not signed** | Receipts are hash references, not cryptographically signed tokens | The hash IS the proof — it references a chain-linked entry. Signing would add key management complexity without meaningfully stronger guarantees since the ledger is the verifier. |

## Live Integration Evidence

### OpenShell (NVIDIA)
- 75 real OCSF events from a live OpenShell sandbox (`ledger-l9`)
- Network deny events captured when sandbox proxy blocked `curl` to `api.github.com`
- Events written through OCSF adapter, chains verified independently

### Kagenti (Red Hat)
- OTEL collector running in Kind cluster (`kagenti-system` namespace)
- Test spans sent via OTLP HTTP endpoint, received by collector
- Spans written through OTEL adapter, chains verified independently

### Cross-System
- Both OpenShell and Kagenti events coexist in the same ledger
- Session-based and trace-ID-based queries return entries from both sources
- Independent chain verification proves no cross-contamination

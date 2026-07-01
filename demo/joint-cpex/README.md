# Joint Demo: Immutable Ledger + CPEX/Praxis

Demonstrates proof receipts integrated with the CPEX composable policy engine.
Every CPEX policy decision — allow, deny, taint, redact, delegation, PII scan —
becomes a hash-chained, verifiable receipt in the immutable ledger.

## Architecture

```
Agent / curl
    │
    ▼
Praxis gateway (:8090)              ← CPEX policy filter
    │   │
    │   └── POST /api/receipts ──→  Ledger REST API (:18099)
    │                                    │
    ▼                                    ▼
HR MCP Server (:9100)               PostgreSQL (:54330)
                                    (hash-chained entries)
```

## Services

| Service | Port | Purpose |
|---|---|---|
| postgres | 54330 | Ledger database |
| ledger | 19292 (gRPC), 18080 (health) | Immutable ledger |
| API gateway | 18099 | REST API for receipts |
| keycloak | 8081 | OIDC IdP (CPEX identity) |
| hr-mcp | 9100 | Mock MCP server |
| valkey | 6379 | Session taint store |
| praxis | 8090 (host) | CPEX gateway (not containerized) |

## Scenarios

| # | Script | CPEX Scenario | What it demonstrates |
|---|---|---|---|
| 01 | bob-allow-receipt.sh | scenario 01 | Allow + delegation → receipt issued + verified |
| 02 | alice-deny-receipt.sh | scenario 02 | APL deny → denial reason recorded in receipt |
| 03 | taint-chain.sh | scenario 08 | Allow → taint → deny → trust chain shows both |
| 04 | redact-inputhash.sh | scenario 03 | SSN redacted → input_hash detects payload change |

## Quick Start

```bash
./run-joint-demo.sh
```

## Prerequisites

- Docker or Podman running
- Python 3.9+ with grpcio
- Ports 54330, 19292, 18080, 18099, 8081, 9100, 6379 free

## Without Praxis

The demo scenarios call the ledger REST API directly, simulating what the
CPEX plugin would do. Praxis is not required to run these scenarios —
the receipt flow is demonstrated end-to-end without the gateway.

When faraujo's CPEX plugin is ready, the scenario scripts become
validation tests for the real integration.

#!/bin/bash
# Shared helpers for joint CPEX + Ledger demo scenarios

LEDGER_API="${LEDGER_API:-http://localhost:18099}"
PRAXIS_URL="${PRAXIS_URL:-http://localhost:8090/mcp}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8081}"
REALM="${REALM:-cpex-demo}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

GREEN="\033[92m"
RED="\033[91m"
CYAN="\033[96m"
PURPLE="\033[95m"
DIM="\033[2m"
BOLD="\033[1m"
RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; }
info() { echo -e "  ${DIM}$1${RESET}"; }

# Issue a receipt and print the result
issue_receipt() {
    local entry_type="$1"
    local agent_id="$2"
    local content="$3"
    local source_id="${4:-praxis-gateway}"
    local correlation_id="${5:-}"
    local input_hash="${6:-}"

    local body=$(python3 -c "
import json
print(json.dumps({
    'entry_type': '$entry_type',
    'agent_id': '$agent_id',
    'content': '$content',
    'source_id': '$source_id',
    'correlation_id': '$correlation_id',
    'input_hash': '$input_hash',
}))
")
    curl -sS "$LEDGER_API/api/receipts" -X POST \
        -H "Content-Type: application/json" \
        -d "$body"
}

# Verify a receipt
verify_receipt() {
    local hash="$1"
    local type="$2"
    curl -sS "$LEDGER_API/api/receipts/verify?hash=$hash&type=$type"
}

# Show trust chain for a correlation ID
show_chain() {
    local corr="$1"
    python3 "$REPO_DIR/proof-explorer/proof.py" receipt-chain --correlation-id "$corr"
}

# Compute SHA-256 of a string
sha256() {
    echo -n "$1" | shasum -a 256 | cut -d' ' -f1
}

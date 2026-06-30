#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROOF="python $REPO_DIR/proof-explorer/proof.py"

BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[92m"
BLUE="\033[94m"
PURPLE="\033[95m"
YELLOW="\033[93m"
RESET="\033[0m"

banner() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
    echo ""
}

section() {
    echo ""
    echo -e "${DIM}───────────────────────────────────────────────────────────${RESET}"
    echo -e "  $1"
    echo -e "${DIM}───────────────────────────────────────────────────────────${RESET}"
    echo ""
}

pause() {
    echo -e "  ${DIM}[Press Enter to continue]${RESET}"
    read -r
}

# ─────────────────────────────────────────────────────────
banner "Immutable Ledger for Agentic Systems — Cross-System Demo"
echo "  This demo proves that independent agentic systems can write"
echo "  to a shared, cryptographically verifiable proof chain without"
echo "  coupling, shared identity, or format standardization."
echo ""
echo "  Three sources. Three identity systems. One verifiable timeline."
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 1: Start the Ledger"
echo "  Starting PostgreSQL + Immutable Ledger via Docker Compose..."
echo ""

cd "$SCRIPT_DIR"
docker compose up -d --build 2>&1 | tail -5

echo ""
echo "  Waiting for ledger to be ready..."
until curl -sf http://localhost:18080/readyz > /dev/null 2>&1; do sleep 1; done
echo -e "  ${GREEN}Ledger ready on gRPC :19092${RESET}"
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 2: Any System Can Write (Standalone Agent)"
echo "  A 50-line Python script writes events to the ledger."
echo "  No SDK. No framework. Just one gRPC call per event."
echo ""

python "$SCRIPT_DIR/01-standalone-writer.py"

section "Verify the standalone chain"
$PROOF verify --entry-type standalone
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 3: Load Cross-System Sample Data"
echo "  Loading realistic events from three independent systems:"
echo ""
echo -e "    ${BLUE}ARE Foundation${RESET}  — authority decisions (passport, scope, policy)"
echo -e "    ${GREEN}OpenShell${RESET}       — sandbox security events (OCSF)"
echo -e "    ${PURPLE}Kagenti${RESET}         — agent execution traces (OTEL)"
echo ""

python "$SCRIPT_DIR/sample-data/load-samples.py"
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 4: Cross-System Query"

section "Query by correlation ID (trace-aaa) — same request, two systems"
$PROOF query --correlation-id trace-aaa

section "Query by correlation ID (trace-bbb) — tool call + sandbox denial"
$PROOF query --correlation-id trace-bbb
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 5: Unified Timeline"

section "Full cross-system timeline (all sources)"
$PROOF timeline --all

section "Ledger summary"
$PROOF summary
pause

# ═══════════════════════════════════════════════════════════
banner "ACT 6: Verify & Detect"

section "Verify all hash chains"
$PROOF verify --all

section "Drift detection — find authorization gaps"
$PROOF drift
pause

# ═══════════════════════════════════════════════════════════
banner "Demo Complete"
echo "  What you just saw:"
echo ""
echo "  1. A standalone agent wrote events with zero dependencies"
echo "  2. Three independent systems wrote to the same ledger:"
echo -e "     ${BLUE}ARE Foundation${RESET} (authority) + ${GREEN}OpenShell${RESET} (isolation) + ${PURPLE}Kagenti${RESET} (orchestration)"
echo "  3. Cross-system queries correlated events by trace ID"
echo "  4. A unified timeline showed the full agent lifecycle"
echo "  5. Independent hash chains verified with zero tampering"
echo "  6. Drift detection found an authorization gap that no"
echo "     single system could have detected alone"
echo ""
echo "  Three identity systems. Three event formats. Zero coupling."
echo "  One verifiable proof chain."
echo ""
echo -e "  ${DIM}To clean up: make -C $SCRIPT_DIR down${RESET}"
echo ""

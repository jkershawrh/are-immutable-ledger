#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOLD="\033[1m"
GREEN="\033[92m"
RED="\033[91m"
DIM="\033[2m"
RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; exit 1; }

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Joint Demo: Immutable Ledger + CPEX/Praxis${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

# ─── Start services ──────────────────────────────
echo -e "${BOLD}Starting services...${RESET}"
cd "$SCRIPT_DIR"

# Check if ledger is already running
if curl -sf http://localhost:18080/readyz > /dev/null 2>&1; then
    ok "Ledger already running"
else
    echo "  Starting compose stack..."
    docker compose up -d --build 2>&1 | tail -3 || \
        podman-compose up -d --build 2>&1 | tail -3 || \
        /Users/jkershaw/Library/Python/3.9/bin/podman-compose up -d --build 2>&1 | tail -3
fi

# ─── Health checks ───────────────────────────────
echo ""
echo -e "${BOLD}Health checks...${RESET}"

echo -n "  Postgres: "
for i in $(seq 1 30); do
    if docker exec demo_postgres_1 pg_isready -U ledger > /dev/null 2>&1 || \
       podman exec demo_postgres_1 pg_isready -U ledger > /dev/null 2>&1 || \
       /opt/podman/bin/podman exec joint-cpex_postgres_1 pg_isready -U ledger > /dev/null 2>&1; then
        ok "healthy"; break
    fi
    sleep 1
done

echo -n "  Ledger: "
for i in $(seq 1 30); do
    if curl -sf http://localhost:18080/readyz > /dev/null 2>&1; then
        ok "healthy (gRPC :19292, REST :18099)"; break
    fi
    sleep 1
done

# Start API gateway if not running
if ! curl -sf http://localhost:18099/api/summary > /dev/null 2>&1; then
    echo "  Starting API gateway..."
    cd "$REPO_DIR"
    python3 api/gateway.py > /dev/null 2>&1 &
    sleep 3
    cd "$SCRIPT_DIR"
fi

if curl -sf http://localhost:18099/api/summary > /dev/null 2>&1; then
    ok "API gateway healthy (:18099)"
else
    fail "API gateway not responding"
fi

# ─── Run scenarios ───────────────────────────────
echo ""
echo -e "${BOLD}Running scenarios...${RESET}"
echo ""

for scenario in "$SCRIPT_DIR"/scenarios/[0-9]*.sh; do
    chmod +x "$scenario"
    bash "$scenario"
    echo ""
done

# ─── Verify all chains ───────────────────────────
echo -e "${BOLD}Verifying all chains...${RESET}"
cd "$REPO_DIR"
python3 proof-explorer/proof.py verify --all 2>&1 | grep -E "VALID|INVALID|All.*chains"
echo ""

# ─── Summary ─────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Demo complete${RESET}"
echo ""
echo "  Every CPEX policy decision — allow, deny, taint, redact,"
echo "  delegation, PII scan — is now a hash-chained, verifiable"
echo "  proof receipt in the immutable ledger."
echo ""
echo -e "  ${DIM}Cleanup: docker compose -f demo/joint-cpex/docker-compose.yml down -v${RESET}"
echo ""

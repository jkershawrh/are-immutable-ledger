#!/bin/bash
# Scenario 03: Session taint chain — allow → taint → deny
# Maps to CPEX scenario 08 + L19.03
set -e
source "$(dirname "$0")/_lib.sh"

echo ""
echo -e "${BOLD}Scenario 03: Session taint chain${RESET}"
echo -e "${DIM}Bob accesses compensation → session tainted → email denied${RESET}"
echo ""

SESSION="taint-chain-$$"

# Step 1: Bob calls get_compensation → allow + taint applied
echo -e "${CYAN}Step 1: Bob accesses compensation data${RESET}"
R1=$(issue_receipt \
    "cpex.compensation.accessed" \
    "bob" \
    "{\"tool\":\"get_compensation\",\"decision\":\"allow\",\"taint_applied\":{\"label\":\"secret\",\"scope\":\"session\"}}" \
    "praxis-gateway" \
    "$SESSION")
H1=$(echo "$R1" | python3 -c "import json,sys; print(json.load(sys.stdin)['entry_hash'])")
ok "Allow receipt: hash=${H1:0:16}... (session tainted with 'secret')"

# Step 2: Bob calls send_email → denied by taint check
echo -e "${RED}Step 2: Bob tries to send email → session taint blocks${RESET}"
R2=$(issue_receipt \
    "cpex.email.denied" \
    "bob" \
    "{\"tool\":\"send_email\",\"decision\":\"deny\",\"reason\":\"session_tainted_secret\",\"taint_labels\":[\"secret\"]}" \
    "praxis-gateway" \
    "$SESSION")
H2=$(echo "$R2" | python3 -c "import json,sys; print(json.load(sys.stdin)['entry_hash'])")
ok "Deny receipt: hash=${H2:0:16}... (session_tainted_secret)"

# Step 3: Show the trust chain
echo ""
echo -e "${PURPLE}Trust chain for session $SESSION:${RESET}"
show_chain "$SESSION"

echo ""
ok "Scenario 03 complete — 2 receipts, 1 session, allow → deny chain"

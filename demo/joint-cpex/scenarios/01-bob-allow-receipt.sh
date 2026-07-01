#!/bin/bash
# Scenario 01: Bob calls get_compensation → allow → receipt issued
# Maps to CPEX scenario 01 + L19.01
set -e
source "$(dirname "$0")/_lib.sh"

echo ""
echo -e "${BOLD}Scenario 01: Bob allow + receipt${RESET}"
echo -e "${DIM}Bob has role.hr → APL gate passes → delegation → receipt issued${RESET}"
echo ""

SESSION="session-01-$$"
REQUEST_BODY='{"employee_id":"EMP-001234","include_ssn":true}'
INPUT_HASH=$(sha256 "$REQUEST_BODY")

# Issue receipt for the allow decision
RECEIPT=$(issue_receipt \
    "cpex.policy.allow" \
    "bob" \
    "{\"tool\":\"get_compensation\",\"decision\":\"allow\",\"policy_steps\":[\"require(role.hr)\",\"delegate(workday-oauth)\"],\"delegated_to\":\"workday-api\"}" \
    "praxis-gateway" \
    "$SESSION" \
    "$INPUT_HASH")

HASH=$(echo "$RECEIPT" | python3 -c "import json,sys; print(json.load(sys.stdin)['entry_hash'])")
echo "$RECEIPT" | python3 -m json.tool

if [ -n "$HASH" ]; then
    ok "Receipt issued: hash=${HASH:0:16}..."
else
    fail "No receipt hash returned"
    exit 1
fi

# Verify the receipt
echo ""
VERIFY=$(verify_receipt "$HASH" "cpex.policy.allow")
VALID=$(echo "$VERIFY" | python3 -c "import json,sys; print(json.load(sys.stdin)['valid'])")

if [ "$VALID" = "True" ]; then
    ok "Receipt verified: valid=true, agent=bob, source=praxis-gateway"
else
    fail "Receipt verification failed"
    echo "$VERIFY" | python3 -m json.tool
    exit 1
fi

echo ""
ok "Scenario 01 complete"

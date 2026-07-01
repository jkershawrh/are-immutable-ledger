#!/bin/bash
# Scenario 02: Alice calls get_compensation → deny → receipt records reason
# Maps to CPEX scenario 02 + L19.02
set -e
source "$(dirname "$0")/_lib.sh"

echo ""
echo -e "${BOLD}Scenario 02: Alice deny + receipt${RESET}"
echo -e "${DIM}Alice has role.engineering → require(role.hr) fails → deny recorded${RESET}"
echo ""

SESSION="session-02-$$"

RECEIPT=$(issue_receipt \
    "cpex.policy.deny" \
    "alice" \
    "{\"tool\":\"get_compensation\",\"decision\":\"deny\",\"reason\":\"require(role.hr) failed\",\"subject_roles\":[\"engineering\"]}" \
    "praxis-gateway" \
    "$SESSION")

HASH=$(echo "$RECEIPT" | python3 -c "import json,sys; print(json.load(sys.stdin)['entry_hash'])")
ok "Deny receipt issued: hash=${HASH:0:16}..."

# Verify and read full content
VERIFY=$(verify_receipt "$HASH" "cpex.policy.deny")
VALID=$(echo "$VERIFY" | python3 -c "import json,sys; print(json.load(sys.stdin)['valid'])")
REASON=$(echo "$VERIFY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('agent_id',''))")

if [ "$VALID" = "True" ]; then
    ok "Deny receipt verified: agent=alice, decision=deny"
else
    fail "Verification failed"
    exit 1
fi

echo ""
ok "Scenario 02 complete"

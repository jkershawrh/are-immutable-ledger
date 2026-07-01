#!/bin/bash
# Scenario 04: Eve's SSN redacted — input_hash detects payload transformation
# Maps to CPEX scenario 03 + L19.04
set -e
source "$(dirname "$0")/_lib.sh"

echo ""
echo -e "${BOLD}Scenario 04: Redaction + input_hash${RESET}"
echo -e "${DIM}Eve lacks view_ssn → SSN redacted → input_hash proves pre/post difference${RESET}"
echo ""

SESSION="redact-$$"
ORIGINAL='{"employee_id":"EMP-001234","ssn":"123-45-6789"}'
REDACTED='{"employee_id":"EMP-001234","ssn":"[REDACTED]"}'
ORIGINAL_HASH=$(sha256 "$ORIGINAL")
REDACTED_HASH=$(sha256 "$REDACTED")

echo -e "  Original payload hash: ${DIM}${ORIGINAL_HASH:0:16}...${RESET}"
echo -e "  Redacted payload hash: ${DIM}${REDACTED_HASH:0:16}...${RESET}"
echo ""

# Receipt issued with ORIGINAL payload hash (before Praxis redacts)
RECEIPT=$(issue_receipt \
    "cpex.policy.allow" \
    "eve" \
    "{\"tool\":\"get_compensation\",\"decision\":\"allow\",\"redacted_fields\":[\"ssn\"]}" \
    "praxis-gateway" \
    "$SESSION" \
    "$ORIGINAL_HASH")

HASH=$(echo "$RECEIPT" | python3 -c "import json,sys; print(json.load(sys.stdin)['entry_hash'])")
ok "Receipt issued with pre-redaction input_hash"

# Verify — get back the input_hash
VERIFY=$(verify_receipt "$HASH" "cpex.policy.allow")
RECEIPT_IH=$(echo "$VERIFY" | python3 -c "import json,sys; print(json.load(sys.stdin)['input_hash'])")

echo ""
echo -e "  Receipt input_hash:    ${DIM}${RECEIPT_IH:0:16}...${RESET}"
echo -e "  Original matches:      $([ "$RECEIPT_IH" = "$ORIGINAL_HASH" ] && echo -e "${GREEN}YES${RESET}" || echo -e "${RED}NO${RESET}")"
echo -e "  Redacted matches:      $([ "$RECEIPT_IH" = "$REDACTED_HASH" ] && echo -e "${GREEN}YES${RESET}" || echo -e "${RED}NO${RESET}")"
echo ""

if [ "$RECEIPT_IH" = "$ORIGINAL_HASH" ] && [ "$RECEIPT_IH" != "$REDACTED_HASH" ]; then
    ok "Downstream can detect: receipt covers PRE-redaction payload, not what it received"
else
    fail "input_hash mismatch logic failed"
    exit 1
fi

echo ""
ok "Scenario 04 complete — payload transformation detectable via input_hash"

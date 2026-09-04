#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_DIR="${1:-${OUT:-}}"
LEDGER_ENDPOINT="${LEDGER_ENDPOINT:-localhost:19292}"
HEALTH_URL="${LEDGER_HEALTH_URL:-http://localhost:18080/readyz}"

if [[ -z "$BUNDLE_DIR" ]]; then
  echo "usage: $0 <AI-Identity demo output directory>" >&2
  echo "       OUT=/path/to/output $0" >&2
  exit 2
fi

RECORDS="$BUNDLE_DIR/records.ndjson"
PUBLIC_KEY="$BUNDLE_DIR/demo-pub.pem"

[[ -f "$RECORDS" ]] || { echo "missing bundle records: $RECORDS" >&2; exit 2; }
[[ -f "$PUBLIC_KEY" ]] || { echo "missing bundle public key: $PUBLIC_KEY" >&2; exit 2; }

echo ""
echo "Verdict to Proof — ledger handoff"
echo "Bundle: $BUNDLE_DIR"

if ! curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
  echo "Starting the ledger compose stack..."
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
  elif [[ -x "$HOME/Library/Python/3.9/bin/podman-compose" ]]; then
    COMPOSE=("$HOME/Library/Python/3.9/bin/podman-compose")
  else
    echo "docker compose or podman-compose is required to start the ledger" >&2
    exit 2
  fi
  "${COMPOSE[@]}" -f "$REPO_DIR/demo/docker-compose.yml" up -d --build

  for _ in $(seq 1 60); do
    curl -sf "$HEALTH_URL" >/dev/null 2>&1 && break
    sleep 1
  done
fi

curl -sf "$HEALTH_URL" >/dev/null || { echo "ledger is not ready at $HEALTH_URL" >&2; exit 1; }

echo "Importing Jeff's six-record NDJSON bundle..."
IMPORT_OUTPUT="$(python3 "$REPO_DIR/adapters/cpex/cpex_to_ledger.py" \
  --endpoint "$LEDGER_ENDPOINT" --strict-gaps --file "$RECORDS" 2>&1)"
echo "$IMPORT_OUTPUT"
echo "$IMPORT_OUTPUT" | grep -Eq "Written: 6[[:space:]]+Errors: 0.*Gaps: 0" || {
  echo "expected six writes with zero errors and zero epoch-scoped gaps" >&2
  exit 1
}

echo "Verifying the ledger's durable cpex chains..."
python3 "$REPO_DIR/proof-explorer/proof.py" verify --entry-type cpex

echo "Verifying conversation and agent correlation across the restart..."
RUN_OUTPUT="$(python3 "$REPO_DIR/proof-explorer/proof.py" query \
  --correlation-id run-4bf92f35)"
echo "$RUN_OUTPUT"
echo "$RUN_OUTPUT" | grep -q "6 entries returned" || {
  echo "expected run-4bf92f35 to correlate all six records" >&2
  exit 1
}

AGENT_OUTPUT="$(python3 "$REPO_DIR/proof-explorer/proof.py" query \
  --agent-id agent-7)"
echo "$AGENT_OUTPUT"
echo "$AGENT_OUTPUT" | grep -q "6 entries returned" || {
  echo "expected agent-7 on all six records" >&2
  exit 1
}

echo "Checking the signed request join key remains in retained content..."
REQUEST_MATCHES="$(python3 - "$RECORDS" <<'PY'
import json
import sys

matches = 0
for line in open(sys.argv[1], encoding="utf-8"):
    if not line.strip():
        continue
    event = json.loads(line)
    if event.get("unmapped", {}).get("cmf.request.request_id") == "corr-7f3e2a91":
        matches += 1
print(matches)
PY
)"
[[ "$REQUEST_MATCHES" == "1" ]] || {
  echo "expected request join key corr-7f3e2a91 on exactly one record" >&2
  exit 1
}
echo "  request join key corr-7f3e2a91 retained on exactly one signed record"

echo "PASS: six signed records imported; identity, correlation, density, and ledger chains verified."
echo "AID-EMIT-1 public key retained at: $PUBLIC_KEY"

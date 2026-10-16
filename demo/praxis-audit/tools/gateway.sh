#!/bin/bash
# Start, stop or kill the Praxis gateway on the host.
#
#   tools/gateway.sh start | stop | kill9 | status
#
# stderr (the OCSF records) is appended to out/gateway.stderr, so a restart
# continues the same file and the next epoch's records follow the last one's.
# GATEWAY_LAUNCHER, if set, prefixes the command (for example to drop
# privileges: Praxis refuses to run as root).
set -euo pipefail
DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$DEMO_DIR/gateway/target/release/praxis-audit-gateway"
PIDFILE="$DEMO_DIR/out/gateway.pid"
mkdir -p "$DEMO_DIR/out"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }
# True only if $1 is a live process whose command line contains our gateway
# binary path. Guards stop/kill9 against a recycled PID or a similarly
# named process that pgrep -x (truncated to 15 chars) might have matched.
pid_is_gateway() {
    local pid="$1"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    ps -p "$pid" -o command= 2>/dev/null | grep -qF "$BIN" || return 1
}
# Wait for the listener to close so a restart can bind the port again.
wait_gone() {
    for _ in $(seq 1 50); do
        curl -s -o /dev/null http://127.0.0.1:8090/ || return 0
        sleep 0.1
    done
}

case "${1:-}" in
    start)
        running && { echo "gateway already running (pid $(cat "$PIDFILE"))"; exit 0; }
        cd "$DEMO_DIR"
        # shellcheck disable=SC2086
        nohup ${GATEWAY_LAUNCHER:-} "$BIN" -c config/praxis.yaml \
            >>out/gateway.log 2>>out/gateway.stderr &
        launched=$!
        for _ in $(seq 1 50); do
            # Any HTTP status means the listener is up.
            if curl -s -o /dev/null http://127.0.0.1:8090/; then
                # Record the gateway's own pid, not a launcher's, so kill9
                # really kills the process holding the audit chain. Verify the
                # pgrep hit is actually our binary before trusting it.
                found="$(pgrep -n -x "$(basename "$BIN" | cut -c1-15)" || true)"
                if pid_is_gateway "$found"; then
                    echo "$found" > "$PIDFILE"
                elif pid_is_gateway "$launched"; then
                    echo "$launched" > "$PIDFILE"
                else
                    echo "gateway listener is up but no matching gateway process found" >&2
                    exit 1
                fi
                exit 0
            fi
            sleep 0.2
        done
        echo "gateway did not come up; see out/gateway.log" >&2
        exit 1
        ;;
    stop)  if running; then
               pid="$(cat "$PIDFILE")"
               pid_is_gateway "$pid" || { echo "refusing: pid $pid is not the gateway ($BIN)" >&2; exit 1; }
               kill "$pid"; wait_gone
           fi; rm -f "$PIDFILE" ;;
    kill9) if running; then
               pid="$(cat "$PIDFILE")"
               pid_is_gateway "$pid" || { echo "refusing: pid $pid is not the gateway ($BIN)" >&2; exit 1; }
               kill -9 "$pid"; wait_gone
           fi; rm -f "$PIDFILE" ;;
    status) running && echo "running (pid $(cat "$PIDFILE"))" || echo "stopped" ;;
    *) echo "usage: $0 start|stop|kill9|status" >&2; exit 2 ;;
esac

#!/usr/bin/env bash
# Run the session suite against the Argus API from another checkout, such as
# a fix branch. Usage: run-against-api.sh <argus-checkout> <evidence-dir>
# Writes http-session-fixed-api.json and exits with the evidence gate's verdict.
# The gate requires that checkout to contain the A14 fix, and A14 to pass.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_TREE="$(cd "$1" && pwd)"
mkdir -p "$2"; OUT="$(cd "$2" && pwd)"
source "$HERE/stack/env.sh"
LOGS="$NATIVE_AUTH_WORK/logs"; mkdir -p "$LOGS"

start_api() {
  pids="$(lsof -tiTCP:"$NATIVE_AUTH_API_PORT" -sTCP:LISTEN || true)"
  [ -n "$pids" ] && kill $pids
  sleep 1
  NATIVE_AUTH_API_ROOT="$1" nohup bash "$HERE/stack/api.sh" > "$LOGS/api-$2.log" 2>&1 &
  for _ in $(seq 1 60); do
    curl -sf "http://127.0.0.1:$NATIVE_AUTH_API_PORT/health" > /dev/null && return
    sleep 1
  done
  echo "API from $1 did not start" >&2; exit 1
}

start_api "$API_TREE" other
set +e
NATIVE_AUTH_API_ROOT="$API_TREE" bash "$HERE/http_probe/run.sh" session --out "$OUT/http-session-fixed-api.json"
STATUS=$?
set -e
start_api "$NATIVE_AUTH_ROOT" default
exit $STATUS

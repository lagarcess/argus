#!/usr/bin/env bash
# Capture every non-interactive suite at the current checkout.
# Usage: run-all.sh <evidence-dir>. Needs stack/up.sh first.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/stack/env.sh"
mkdir -p "$1"; OUT="$(cd "$1" && pwd)"
LOGS="$NATIVE_AUTH_WORK/logs"; mkdir -p "$LOGS"

restart_services() {
  for port in "$NATIVE_AUTH_API_PORT" "$NATIVE_AUTH_ADAPTER_PORT"; do
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN || true)"
    [ -n "$pids" ] && kill $pids
  done
  sleep 1
  nohup bash "$HERE/stack/api.sh" > "$LOGS/api.log" 2>&1 &
  nohup bash "$HERE/adapter/run.sh" > "$LOGS/adapter.log" 2>&1 &
  for _ in $(seq 1 60); do
    curl -sf "http://127.0.0.1:$NATIVE_AUTH_API_PORT/health" > /dev/null \
      && curl -sf "http://127.0.0.1:$NATIVE_AUTH_ADAPTER_PORT/health" > /dev/null && return
    sleep 1
  done
  echo "services did not start" >&2; exit 1
}
captcha_mode() {
  bash "$HERE/stack/restart-auth.sh" "$1" > "$LOGS/restart-$1.log" 2>&1
  restart_services
}

captcha_mode off
bash "$HERE/http_probe/run.sh" session --out "$OUT/http-session.json"
bash "$HERE/http_probe/run.sh" guest --out "$OUT/http-guest.json"
bash "$HERE/http_probe/run.sh" guest-adapter --out "$OUT/http-guest-adapter.json"
bash "$HERE/http_probe/run.sh" callbacks --out "$OUT/http-callbacks.json"
for mode in turnstile-pass turnstile-fail turnstile-spent; do
  captcha_mode "$mode"
  bash "$HERE/http_probe/run.sh" captcha --captcha-mode "$mode" --out "$OUT/http-captcha-$mode.json"
done
captcha_mode off
bash "$HERE/ios/run-simulator-tests.sh" "$OUT/ios-simulator.json" || echo "iOS suite reported failures (see ios-simulator.json)"

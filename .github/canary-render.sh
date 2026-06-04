#!/bin/bash
# Authenticated golden-path canary for the private-alpha Render deployment.

set -euo pipefail

APP_URL="${ARGUS_CANARY_APP_URL:-https://argus-app-suz5.onrender.com}"
API_URL="${ARGUS_CANARY_API_URL:-https://argus-ohr5.onrender.com}"
EMAIL="${ARGUS_CANARY_EMAIL:-}"
PASSWORD="${ARGUS_CANARY_PASSWORD:-}"
SUPABASE_URL="${ARGUS_CANARY_SUPABASE_URL:-}"
SUPABASE_SERVICE_ROLE_KEY="${ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY:-}"
TIMEOUT_SECONDS="${ARGUS_CANARY_TIMEOUT_SECONDS:-240}"
PROMPT="${ARGUS_CANARY_PROMPT:-Test an equal-weight AAPL and MSFT strategy from 2025 to 2026 to date}"

if [ -z "$EMAIL" ]; then
  echo "ARGUS_CANARY_EMAIL is required."
  exit 1
fi

if [ -z "$PASSWORD" ]; then
  echo "ARGUS_CANARY_PASSWORD is required."
  exit 1
fi

COOKIE_JAR="$(mktemp)"
CONFIRMATION_STREAM="$(mktemp)"
RUN_STREAM="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$CONFIRMATION_STREAM" "$RUN_STREAM"' EXIT

.github/warmup-render.sh

LOGIN_BODY="$(
  CANARY_EMAIL="$EMAIL" CANARY_PASSWORD="$PASSWORD" python3 - <<'PY'
import json
import os

print(json.dumps({
    "email": os.environ["CANARY_EMAIL"],
    "password": os.environ["CANARY_PASSWORD"],
}))
PY
)"

echo "Logging in canary user: $EMAIL"
curl -fsS \
  -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_BODY" \
  "${API_URL}/api/v1/auth/login" >/dev/null

CONVERSATION_ID="$(
  curl -fsS \
    -b "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "{}" \
    "${API_URL}/api/v1/conversations" |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["conversation"]["id"])'
)"

CHAT_BODY="$(
  CONVERSATION_ID="$CONVERSATION_ID" PROMPT="$PROMPT" python3 - <<'PY'
import json
import os

print(json.dumps({
    "conversation_id": os.environ["CONVERSATION_ID"],
    "message": os.environ["PROMPT"],
    "language": "en",
}))
PY
)"

echo "Created canary conversation: $CONVERSATION_ID"
curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$CHAT_BODY" \
  "${API_URL}/api/v1/chat/stream" > "$CONFIRMATION_STREAM"

python3 - "$CONFIRMATION_STREAM" <<'PY'
import json
import pathlib
import sys

stream = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
events = []
for part in stream.split("\n\n"):
    for line in part.splitlines():
        if line.startswith("data: "):
            raw = line.removeprefix("data: ").strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))
if "data: [DONE]" not in stream:
    raise SystemExit("confirmation stream did not finish")
if any(event.get("type") == "error" for event in events):
    raise SystemExit("confirmation stream returned error")
if not any(
    event.get("type") == "final" and event.get("payload", {}).get("confirmation")
    for event in events
):
    raise SystemExit("confirmation stream did not return a confirmation")
PY

# Canary action includes "type":"run_backtest".
RUN_BODY="$(
  CONVERSATION_ID="$CONVERSATION_ID" python3 - <<'PY'
import json
import os

print(json.dumps({
    "conversation_id": os.environ["CONVERSATION_ID"],
    "action": {
        "type": "run_backtest",
        "label": "Run backtest",
        "presentation": "confirmation",
        "payload": {},
    },
    "language": "en",
}))
PY
)"

curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$RUN_BODY" \
  "${API_URL}/api/v1/chat/stream" > "$RUN_STREAM"

python3 - "$RUN_STREAM" <<'PY'
import json
import pathlib
import sys

stream = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
events = []
for part in stream.split("\n\n"):
    for line in part.splitlines():
        if line.startswith("data: "):
            raw = line.removeprefix("data: ").strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))
if "data: [DONE]" not in stream:
    raise SystemExit("run stream did not finish")
if any(event.get("type") == "error" for event in events):
    raise SystemExit("run stream returned error")
finals = [event.get("payload", {}) for event in events if event.get("type") == "final"]
if not finals:
    raise SystemExit("run stream did not return final payload")
if not any(payload.get("run") for payload in finals):
    raise SystemExit("run stream did not persist a backtest_run")
PY

MESSAGES_JSON="$(
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages"
)"

python3 - "$MESSAGES_JSON" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
roles = [item.get("role") for item in payload.get("items", [])]
if roles.count("user") < 1 or roles.count("assistant") < 2:
    raise SystemExit("conversation did not persist expected user and assistant messages")
PY

if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  BACKTEST_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/backtest_runs?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"
  RECEIPT_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/route_receipts?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"
  python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" <<'PY'
import json
import sys

backtest_rows = json.loads(sys.argv[1])
receipt_rows = json.loads(sys.argv[2])
if not backtest_rows:
    raise SystemExit("Supabase verifier did not find canary backtest_run")
if not receipt_rows:
    raise SystemExit("Supabase verifier did not find canary route_receipts")
PY
else
  echo "Skipping Supabase verifier; set ARGUS_CANARY_SUPABASE_URL and ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY to verify DB rows."
fi

echo "Canary passed: confirmation, run_backtest action, backtest_run, and messages are present."

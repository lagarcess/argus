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
POLL_SLEEP_SECONDS="${ARGUS_CANARY_POLL_SLEEP_SECONDS:-5}"
PROMPT="${ARGUS_CANARY_PROMPT:-Test an equal-weight AAPL and MSFT buy-and-hold strategy from January 1, 2025 through June 5, 2026 with 10,000 dollars}"

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
JOB_RESPONSE="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$CONFIRMATION_STREAM" "$RUN_STREAM" "$JOB_RESPONSE"' EXIT

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

RUN_ACTION="$(
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

confirmations = []
for event in events:
    if event.get("type") != "final":
        continue
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        continue
    for key in ("confirmation", "confirmation_card"):
        value = payload.get(key)
        if isinstance(value, dict):
            confirmations.append(value)
    final_response_payload = payload.get("final_response_payload")
    if isinstance(final_response_payload, dict):
        for key in ("confirmation", "confirmation_card"):
            value = final_response_payload.get(key)
            if isinstance(value, dict):
                confirmations.append(value)

if not confirmations:
    raise SystemExit("confirmation stream did not return a confirmation")

for confirmation in confirmations:
    for action in confirmation.get("actions") or []:
        if isinstance(action, dict) and action.get("type") == "run_backtest":
            print(json.dumps(action, sort_keys=True))
            raise SystemExit(0)

raise SystemExit("confirmation stream did not include run_backtest action")
PY
)"

RUN_BODY="$(
  CONVERSATION_ID="$CONVERSATION_ID" RUN_ACTION="$RUN_ACTION" python3 - <<'PY'
import json
import os

print(json.dumps({
    "conversation_id": os.environ["CONVERSATION_ID"],
    "action": json.loads(os.environ["RUN_ACTION"]),
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

RUN_RESULT="$(
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
for payload in finals:
    job = payload.get("backtest_job")
    if not isinstance(job, dict):
        final_response_payload = payload.get("final_response_payload")
        if isinstance(final_response_payload, dict):
            job = final_response_payload.get("backtest_job")
    if isinstance(job, dict) and job.get("id"):
        print(f"job:{job['id']}")
        raise SystemExit(0)
for payload in finals:
    run = payload.get("run")
    if isinstance(run, dict) and run.get("id"):
        print(f"run:{run['id']}")
        raise SystemExit(0)
raise SystemExit("run stream returned neither backtest_job nor backtest_run")
PY
)"

BACKTEST_JOB_ID=""
poll_backtest_job() {
  local job_id="$1"
  local poll_deadline=$((SECONDS + TIMEOUT_SECONDS))
  local poll_result

  echo "Polling backtest job: $job_id"
  while true; do
    curl -fsS \
      -b "$COOKIE_JAR" \
      "${API_URL}/api/v1/backtest-jobs/${job_id}" > "$JOB_RESPONSE"
    poll_result="$(
      python3 - "$JOB_RESPONSE" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
job = payload.get("job")
if not isinstance(job, dict):
    raise SystemExit("job status response did not include job")
status = str(job.get("status") or "")
if status == "succeeded":
    run = payload.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        raise SystemExit("backtest job succeeded without linked run")
    source = payload.get("result_readout_source")
    fallback_used = payload.get("result_readout_fallback_used")
    if source != "llm_explain_stage" or fallback_used is not False:
        raise SystemExit(
            "backtest job did not preserve LLM result readout voice: "
            f"source={source!r} fallback_used={fallback_used!r}"
        )
    print(f"succeeded:{run['id']}")
elif status in {"failed", "canceled", "expired"}:
    detail = job.get("failure_detail") or job.get("failure_code") or ""
    print(f"terminal:{status}:{detail}")
else:
    print(f"pending:{status or 'unknown'}")
PY
    )"
    case "$poll_result" in
      succeeded:*)
        echo "OK: backtest job completed with run ${poll_result#succeeded:}"
        return 0
        ;;
      terminal:*)
        echo "ERROR: backtest job ended unsuccessfully: $poll_result"
        cat "$JOB_RESPONSE"
        return 1
        ;;
      pending:*)
        if [ "$SECONDS" -ge "$poll_deadline" ]; then
          echo "ERROR: backtest job did not complete within ${TIMEOUT_SECONDS}s"
          cat "$JOB_RESPONSE"
          return 1
        fi
        echo "  waiting for backtest job... ${poll_result#pending:}"
        sleep "$POLL_SLEEP_SECONDS"
        ;;
      *)
        echo "ERROR: unknown backtest job poll result: $poll_result"
        cat "$JOB_RESPONSE"
        return 1
        ;;
    esac
  done
}

case "$RUN_RESULT" in
  job:*)
    BACKTEST_JOB_ID="${RUN_RESULT#job:}"
    poll_backtest_job "$BACKTEST_JOB_ID"
    ;;
  run:*)
    echo "OK: run stream returned immediate run ${RUN_RESULT#run:}"
    ;;
  *)
    echo "ERROR: unknown run stream result: $RUN_RESULT"
    exit 1
    ;;
esac

MESSAGES_JSON="$(
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages"
)"

CANARY_JOB_ID="$BACKTEST_JOB_ID" python3 - "$MESSAGES_JSON" <<'PY'
import json
import os
import sys

payload = json.loads(sys.argv[1])
roles = [item.get("role") for item in payload.get("items", [])]
if roles.count("user") < 1 or roles.count("assistant") < 2:
    raise SystemExit("conversation did not persist expected user and assistant messages")
job_id = os.environ.get("CANARY_JOB_ID", "")
if job_id:
    for item in payload.get("items", []):
        metadata = item.get("metadata") or {}
        job = metadata.get("backtest_job")
        if isinstance(job, dict) and job.get("id") == job_id:
            break
    else:
        raise SystemExit("conversation did not persist async backtest_job metadata")
PY

if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  BACKTEST_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/backtest_runs?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"
  JOB_ROWS="[]"
  if [ -n "$BACKTEST_JOB_ID" ]; then
    JOB_ROWS="$(
      curl -fsS \
        -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
        "${SUPABASE_URL}/rest/v1/backtest_jobs?select=id,status,result_run_id,execution_metadata&id=eq.${BACKTEST_JOB_ID}&limit=1"
    )"
  fi
  RESULT_RUN_ID="$(
    python3 - "$JOB_ROWS" "$BACKTEST_JOB_ID" <<'PY'
import json
import sys

job_rows = json.loads(sys.argv[1])
job_id = sys.argv[2]
if job_id and job_rows:
    print(str(job_rows[0].get("result_run_id") or "").strip())
PY
  )"
  RECEIPT_ROWS="[]"
  if [ -n "$RESULT_RUN_ID" ]; then
    RECEIPT_ROWS="$(
      curl -fsS \
        -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
        "${SUPABASE_URL}/rest/v1/route_receipts?select=id&conversation_id=eq.${CONVERSATION_ID}&run_id=eq.${RESULT_RUN_ID}&task=eq.result_summary&limit=1"
    )"
  fi
  python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" "$JOB_ROWS" "$BACKTEST_JOB_ID" "$RESULT_RUN_ID" <<'PY'
import json
import sys

backtest_rows = json.loads(sys.argv[1])
receipt_rows = json.loads(sys.argv[2])
job_rows = json.loads(sys.argv[3])
job_id = sys.argv[4]
expected_result_run_id = sys.argv[5]
if not backtest_rows:
    raise SystemExit("Supabase verifier did not find canary backtest_run")
if job_id and not job_rows:
    raise SystemExit("Supabase verifier did not find canary backtest_job")
if job_id:
    job = job_rows[0]
    result_run_id = str(job.get("result_run_id") or "").strip()
    if not result_run_id:
        raise SystemExit("Supabase verifier found canary backtest_job without result_run_id")
    if result_run_id != expected_result_run_id:
        raise SystemExit("Supabase verifier result_run_id changed during verification")
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        raise SystemExit("Supabase verifier found canary backtest_job without execution_metadata")
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        raise SystemExit(
            "Supabase verifier found canary backtest_job without workflow_backtest metadata"
        )
    source = workflow_metadata.get("result_readout_source")
    fallback_used = workflow_metadata.get("result_readout_fallback_used")
    if source != "llm_explain_stage" or fallback_used is not False:
        raise SystemExit(
            "Supabase verifier found non-LLM result readout voice: "
            f"source={source!r} fallback_used={fallback_used!r}"
        )
    if not receipt_rows:
        raise SystemExit(
            "Supabase verifier did not find canary result_summary route_receipts"
        )
PY
else
  echo "Skipping Supabase verifier; set ARGUS_CANARY_SUPABASE_URL and ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY to verify DB rows."
fi

echo "Canary passed: confirmation, run_backtest action, async job/run result, LLM readout voice, and messages are present."

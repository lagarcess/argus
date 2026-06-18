#!/bin/bash
# Authenticated golden-path canary for the private-alpha Render deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/argus-env.sh"
argus_load_root_env >/dev/null || true

APP_URL="${ARGUS_CANARY_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"
API_URL="${ARGUS_CANARY_API_URL:-$ARGUS_PRIVATE_LAUNCH_API_URL}"
EMAIL="${ARGUS_CANARY_EMAIL:-${MOCK_USER_EMAIL:-}}"
PASSWORD="${ARGUS_CANARY_PASSWORD:-${MOCK_USER_PASSWORD:-}}"
SUPABASE_URL="${ARGUS_CANARY_SUPABASE_URL:-${SUPABASE_URL:-${SUPABASE_PROJECT_URL:-}}}"
SUPABASE_SERVICE_ROLE_KEY="${ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"
TIMEOUT_SECONDS="${ARGUS_CANARY_TIMEOUT_SECONDS:-240}"
POLL_SLEEP_SECONDS="${ARGUS_CANARY_POLL_SLEEP_SECONDS:-5}"
LANGUAGE="${ARGUS_CANARY_LANGUAGE:-en}"
EXPECT_MODE="${ARGUS_CANARY_EXPECT_MODE:-${ARGUS_WARMUP_EXPECT_MODE:-real-workflow}}"
EVIDENCE_PATH="${ARGUS_CANARY_EVIDENCE_PATH:-}"
CANDIDATE_SHA="${ARGUS_CANARY_SHA:-${GITHUB_SHA:-}}"
CHECKED_OUT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
PROMPT="${ARGUS_CANARY_PROMPT:-Test an equal-weight AAPL and MSFT buy-and-hold strategy from January 1, 2025 through June 5, 2026 with 10,000 dollars}"

if [ -z "$CHECKED_OUT_SHA" ]; then
  CHECKED_OUT_SHA="unknown"
fi

if [ -z "$CANDIDATE_SHA" ]; then
  CANDIDATE_SHA="$CHECKED_OUT_SHA"
fi

privacy_safe_id_label() {
  local label_type="$1"
  local raw_value="$2"
  if [ -z "$raw_value" ]; then
    echo ""
    return 0
  fi
  CANARY_ID_VALUE="$raw_value" python3 - "$label_type" <<'PY'
import hashlib
import os
import sys

prefix = sys.argv[1]
raw_value = os.environ["CANARY_ID_VALUE"]
label = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:12]
print(f"{prefix}_{label}")
PY
}

print_safe_job_response() {
  python3 - "$JOB_RESPONSE" <<'PY'
import json
import pathlib
import sys

try:
    payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    print("job response summary unavailable")
    raise SystemExit(0)

job = payload.get("job") if isinstance(payload, dict) else None
summary = {}
if isinstance(job, dict):
    status = job.get("status")
    if status:
        summary["job_status"] = status
    failure_code = job.get("failure_code")
    if failure_code:
        summary["failure_code"] = failure_code
source = payload.get("result_readout_source") if isinstance(payload, dict) else None
fallback_used = payload.get("result_readout_fallback_used") if isinstance(payload, dict) else None
if source:
    summary["result_readout_source"] = source
if fallback_used is not None:
    summary["result_readout_fallback_used"] = fallback_used
print(json.dumps(summary or {"job_response": "present"}, sort_keys=True))
PY
}

WARMUP_OUTPUT=""
API_DEPLOY_STATUS_OUTPUT=""
WEB_DEPLOY_STATUS_OUTPUT=""
print_sanitized_warmup_output() {
  CANARY_WARMUP_OUTPUT="$WARMUP_OUTPUT" python3 - <<'PY'
import json
import os

for line in os.environ["CANARY_WARMUP_OUTPUT"].splitlines():
    stripped = line.strip()
    if not stripped:
        print(line)
        continue
    if stripped.startswith("{") and (
        '"unresolved_jobs"' in stripped
        or '"user_id"' in stripped
        or '"task_run_id"' in stripped
    ):
        try:
            report = json.loads(stripped)
        except json.JSONDecodeError:
            print("stale_job_scan_output=<redacted>")
            continue
        print(
            "stale_job_scan_status="
            f"{report.get('status', '<unknown>')} "
            f"scanned={report.get('scanned_count', '<unknown>')} "
            f"stale={report.get('stale_count', '<unknown>')} "
            f"reconciled={report.get('reconciled_count', '<unknown>')} "
            f"unresolved={report.get('unresolved_count', '<unknown>')} "
            f"errors={report.get('error_count', '<unknown>')}"
        )
        continue
    if stripped.startswith("unresolved stale job:"):
        print("unresolved stale job: <redacted>")
        continue
    if any(token in stripped for token in ("user_id", "task_run_id", "unresolved_jobs")):
        print("stale_job_scan_output=<redacted>")
        continue
    print(line)
PY
}

run_warmup_probe() {
  if ! WARMUP_OUTPUT="$(.github/warmup-render.sh --expect-mode "$EXPECT_MODE")"; then
    print_sanitized_warmup_output
    fail_canary "warmup" "warmup_probe_failed"
  fi
  print_sanitized_warmup_output
}

extract_warmup_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); found=1; exit } END { if (!found) exit 1 }' <<< "$WARMUP_OUTPUT"
}

extract_status_value() {
  local status="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); found=1; exit } END { if (!found) exit 1 }' <<< "$status"
}

run_deploy_status_probe() {
  if ! API_DEPLOY_STATUS_OUTPUT="$("$SCRIPT_DIR/render-env-sync.sh" api-deploy-status)"; then
    fail_canary "deploy_status" "api_deploy_status_failed"
  fi
  if ! WEB_DEPLOY_STATUS_OUTPUT="$("$SCRIPT_DIR/render-env-sync.sh" web-deploy-status)"; then
    fail_canary "deploy_status" "web_deploy_status_failed"
  fi

  API_DEPLOY_SHA="$(extract_status_value "$API_DEPLOY_STATUS_OUTPUT" commit || true)"
  WEB_DEPLOY_SHA="$(extract_status_value "$WEB_DEPLOY_STATUS_OUTPUT" commit || true)"
  API_DEPLOY_STATUS="$(extract_status_value "$API_DEPLOY_STATUS_OUTPUT" status || true)"
  WEB_DEPLOY_STATUS="$(extract_status_value "$WEB_DEPLOY_STATUS_OUTPUT" status || true)"

  if [ -z "$API_DEPLOY_SHA" ] || [ "$API_DEPLOY_SHA" = "<missing>" ]; then
    fail_canary "deploy_status" "api_deploy_sha_missing"
  fi
  if [ -z "$WEB_DEPLOY_SHA" ] || [ "$WEB_DEPLOY_SHA" = "<missing>" ]; then
    fail_canary "deploy_status" "web_deploy_sha_missing"
  fi
  if [ "$API_DEPLOY_STATUS" != "live" ]; then
    echo "ERROR: argus-api latest deploy is not live."
    fail_canary "deploy_status" "api_deploy_not_live"
  fi
  if [ "$WEB_DEPLOY_STATUS" != "live" ]; then
    echo "ERROR: argus-app latest deploy is not live."
    fail_canary "deploy_status" "web_deploy_not_live"
  fi
  if [ "$API_DEPLOY_SHA" != "$CANDIDATE_SHA" ]; then
    echo "ERROR: argus-api deploy SHA does not match candidate SHA."
    fail_canary "deploy_status" "api_deploy_sha_mismatch"
  fi
  if [ "$WEB_DEPLOY_SHA" != "$CANDIDATE_SHA" ]; then
    echo "ERROR: argus-app deploy SHA does not match candidate SHA."
    fail_canary "deploy_status" "web_deploy_sha_mismatch"
  fi

  echo "canary_api_deploy_status=$API_DEPLOY_STATUS"
  echo "canary_web_deploy_status=$WEB_DEPLOY_STATUS"
  echo "canary_api_deploy_sha=$API_DEPLOY_SHA"
  echo "canary_web_deploy_sha=$WEB_DEPLOY_SHA"
}

validate_release_evidence_contract() {
  if [ "$CANDIDATE_SHA" != "unknown" ] && [ "$CHECKED_OUT_SHA" != "unknown" ] && [ "$CANDIDATE_SHA" != "$CHECKED_OUT_SHA" ]; then
    echo "ERROR: canary commit mismatch: expected ${CANDIDATE_SHA}, checked out ${CHECKED_OUT_SHA}"
    fail_canary "commit" "canary_commit_mismatch"
  fi

  run_deploy_status_probe
  run_warmup_probe

  ENV_FINGERPRINT="$(extract_warmup_value env_fingerprint || true)"
  WORKFLOW_TASK="$(extract_warmup_value workflow_task || true)"
  REAL_WORKFLOW_TASK="$(extract_warmup_value real_workflow_task || true)"

  if [[ ! "$ENV_FINGERPRINT" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ERROR: release config audit did not emit a valid env_fingerprint."
    fail_canary "warmup" "missing_env_fingerprint"
  fi
  if [ -z "$WORKFLOW_TASK" ]; then
    echo "ERROR: release config audit did not emit workflow_task."
    fail_canary "warmup" "missing_workflow_task"
  fi
  if [ -z "$REAL_WORKFLOW_TASK" ]; then
    echo "ERROR: release config audit did not emit real_workflow_task."
    fail_canary "warmup" "missing_real_workflow_task"
  fi

  echo "canary_expected_mode=$EXPECT_MODE"
  echo "canary_env_fingerprint=$ENV_FINGERPRINT"
  echo "canary_workflow_task=$WORKFLOW_TASK"
  echo "canary_real_workflow_task=$REAL_WORKFLOW_TASK"
  echo "canary_expected_sha=$CANDIDATE_SHA"
  echo "canary_checked_out_sha=$CHECKED_OUT_SHA"
  echo "canary_language=$LANGUAGE"
}

write_canary_evidence() {
  if [ -z "$EVIDENCE_PATH" ]; then
    return 0
  fi

  mkdir -p "$(dirname "$EVIDENCE_PATH")"
  CANARY_EVIDENCE_PATH="$EVIDENCE_PATH" \
  CANARY_STATUS="$CANARY_STATUS" \
  CANARY_FAILURE_STAGE="$CANARY_FAILURE_STAGE" \
  CANARY_FAILURE_REASON="$CANARY_FAILURE_REASON" \
  CANARY_EXPECTED_MODE="$EXPECT_MODE" \
  CANARY_ENV_FINGERPRINT="$ENV_FINGERPRINT" \
  CANARY_WORKFLOW_TASK="$WORKFLOW_TASK" \
  CANARY_REAL_WORKFLOW_TASK="$REAL_WORKFLOW_TASK" \
  CANARY_API_DEPLOY_SHA="$API_DEPLOY_SHA" \
  CANARY_WEB_DEPLOY_SHA="$WEB_DEPLOY_SHA" \
  CANARY_API_DEPLOY_STATUS="$API_DEPLOY_STATUS" \
  CANARY_WEB_DEPLOY_STATUS="$WEB_DEPLOY_STATUS" \
  CANARY_EXPECTED_SHA="$CANDIDATE_SHA" \
  CANARY_CHECKED_OUT_SHA="$CHECKED_OUT_SHA" \
  CANARY_LANGUAGE="$LANGUAGE" \
  CANARY_CONVERSATION_LABEL="$CONVERSATION_LABEL" \
  CANARY_BACKTEST_JOB_LABEL="$BACKTEST_JOB_LABEL" \
  CANARY_RESULT_LABEL="$RESULT_LABEL" \
  CANARY_RESULT_KIND="$RESULT_KIND" \
  python3 - <<'PY'
import json
import os
import pathlib

path = pathlib.Path(os.environ["CANARY_EVIDENCE_PATH"])
payload = {
    "status": os.environ["CANARY_STATUS"],
    "failure_stage": os.environ["CANARY_FAILURE_STAGE"] or None,
    "failure_reason": os.environ["CANARY_FAILURE_REASON"] or None,
    "expected_mode": os.environ["CANARY_EXPECTED_MODE"],
    "env_fingerprint": os.environ["CANARY_ENV_FINGERPRINT"],
    "workflow_task": os.environ["CANARY_WORKFLOW_TASK"],
    "real_workflow_task": os.environ["CANARY_REAL_WORKFLOW_TASK"],
    "api_deploy_sha": os.environ["CANARY_API_DEPLOY_SHA"] or None,
    "web_deploy_sha": os.environ["CANARY_WEB_DEPLOY_SHA"] or None,
    "api_deploy_status": os.environ["CANARY_API_DEPLOY_STATUS"] or None,
    "web_deploy_status": os.environ["CANARY_WEB_DEPLOY_STATUS"] or None,
    "candidate_sha": os.environ["CANARY_EXPECTED_SHA"],
    "checked_out_sha": os.environ["CANARY_CHECKED_OUT_SHA"],
    "language": os.environ["CANARY_LANGUAGE"],
    "conversation_label": os.environ["CANARY_CONVERSATION_LABEL"],
    "backtest_job_label": os.environ["CANARY_BACKTEST_JOB_LABEL"] or None,
    "result_label": os.environ["CANARY_RESULT_LABEL"] or None,
    "result_kind": os.environ["CANARY_RESULT_KIND"] or None,
    "privacy": "no_raw_ids; labels are sha256 prefixes",
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"canary_evidence_path={path}")
PY
}

fail_canary() {
  CANARY_STATUS="failed"
  CANARY_FAILURE_STAGE="$1"
  CANARY_FAILURE_REASON="$2"
  if ! write_canary_evidence; then
    echo "ERROR: failed to write canary evidence."
  fi
  exit 1
}

fetch_conversation_messages() {
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages"
}

assert_reload_hydration_payload() {
  local require_success_messages="$1"
  CANARY_JOB_ID="$BACKTEST_JOB_ID" \
  CANARY_REQUIRE_SUCCESS_MESSAGES="$require_success_messages" \
  python3 - "$MESSAGES_JSON" <<'PY'
import json
import os
import sys

payload = json.loads(sys.argv[1])
items = payload.get("items", [])
require_success_messages = os.environ.get("CANARY_REQUIRE_SUCCESS_MESSAGES") == "true"

if require_success_messages:
    roles = [item.get("role") for item in items]
    if roles.count("user") < 1 or roles.count("assistant") < 2:
        raise SystemExit("conversation did not persist expected user and assistant messages")
    job_id = os.environ.get("CANARY_JOB_ID", "")
    if job_id:
        for item in items:
            metadata = item.get("metadata") or {}
            job = metadata.get("backtest_job")
            if isinstance(job, dict) and job.get("id") == job_id:
                break
        else:
            raise SystemExit("conversation did not persist async backtest_job metadata")

def _has_authoritative_result(metadata: dict) -> bool:
    if not isinstance(metadata, dict):
        return False
    if isinstance(metadata.get("backtest_job"), dict):
        return True
    for key in ("backtest_run", "result_card", "conversation_result_card"):
        if isinstance(metadata.get(key), dict):
            return True
    return bool(metadata.get("result_run_id") or metadata.get("latest_run_id"))

def assert_no_reload_contradiction(hydrated_items: list[dict]) -> None:
    authoritative_result_seen = any(
        item.get("role") == "assistant"
        and _has_authoritative_result(item.get("metadata") or {})
        for item in hydrated_items
    )
    if not authoritative_result_seen:
        return

    stale_retryable_failure_seen = False
    for item in hydrated_items:
        if item.get("role") != "assistant":
            continue
        metadata = item.get("metadata") or {}
        recovery = metadata.get("recovery")
        retryable_recovery = isinstance(recovery, dict) and recovery.get("retryable") is True
        retry_action = "retry_last_turn" in metadata
        runtime_failure = (
            metadata.get("conversation_mode") == "recovery"
            or metadata.get("agent_runtime_stage_outcome") == "agent_runtime_failure"
        )
        superseded = metadata.get("agent_runtime_failure_superseded") is True
        if (retryable_recovery or retry_action or runtime_failure) and not superseded:
            stale_retryable_failure_seen = True
            break

    if stale_retryable_failure_seen:
        raise SystemExit(
            "reload hydration contradiction: retryable failure persisted beside authoritative result"
        )

assert_no_reload_contradiction(items)
PY
}

handle_stream_failure() {
  local stream_name="$1"
  echo "ERROR: ${stream_name} stream failed; checking reload hydration after stream failure."
  if MESSAGES_JSON="$(fetch_conversation_messages)"; then
    if ! assert_reload_hydration_payload false; then
      fail_canary "${stream_name}_stream" "stream_failure_reload_contradiction"
    fi
  else
    echo "ERROR: unable to fetch conversation messages after ${stream_name} stream failure."
  fi
  fail_canary "${stream_name}_stream" "stream_transport_failed"
}

COOKIE_JAR="$(mktemp)"
CONFIRMATION_STREAM="$(mktemp)"
RUN_STREAM="$(mktemp)"
JOB_RESPONSE="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$CONFIRMATION_STREAM" "$RUN_STREAM" "$JOB_RESPONSE"' EXIT

ENV_FINGERPRINT=""
WORKFLOW_TASK=""
REAL_WORKFLOW_TASK=""
API_DEPLOY_SHA=""
WEB_DEPLOY_SHA=""
API_DEPLOY_STATUS=""
WEB_DEPLOY_STATUS=""
CONVERSATION_LABEL=""
BACKTEST_JOB_LABEL=""
RESULT_LABEL=""
RESULT_KIND=""
BACKTEST_RUN_ID=""
MESSAGES_JSON=""
CANARY_STATUS="running"
CANARY_FAILURE_STAGE=""
CANARY_FAILURE_REASON=""

if [ -z "$EMAIL" ]; then
  echo "ARGUS_CANARY_EMAIL or MOCK_USER_EMAIL is required."
  fail_canary "auth" "missing_canary_email"
fi

if [ -z "$PASSWORD" ]; then
  echo "ARGUS_CANARY_PASSWORD or MOCK_USER_PASSWORD is required."
  fail_canary "auth" "missing_canary_password"
fi

validate_release_evidence_contract

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

echo "Logging in canary user"
if ! curl -fsS \
  -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_BODY" \
  "${API_URL}/api/v1/auth/login" >/dev/null; then
  fail_canary "auth" "login_failed"
fi

if ! CONVERSATION_ID="$(
  curl -fsS \
    -b "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "{}" \
    "${API_URL}/api/v1/conversations" |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["conversation"]["id"])'
)"; then
  fail_canary "conversation" "conversation_create_failed"
fi
CONVERSATION_LABEL="$(privacy_safe_id_label conversation "$CONVERSATION_ID")"

CHAT_BODY="$(
  CONVERSATION_ID="$CONVERSATION_ID" PROMPT="$PROMPT" CANARY_LANGUAGE="$LANGUAGE" python3 - <<'PY'
import json
import os

print(json.dumps({
    "conversation_id": os.environ["CONVERSATION_ID"],
    "message": os.environ["PROMPT"],
    "language": os.environ["CANARY_LANGUAGE"],
}))
PY
)"

echo "Created canary conversation: $CONVERSATION_LABEL"
if ! curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$CHAT_BODY" \
  "${API_URL}/api/v1/chat/stream" > "$CONFIRMATION_STREAM"; then
  handle_stream_failure "confirmation"
fi

if ! RUN_ACTION="$(
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
)"; then
  fail_canary "confirmation_stream" "confirmation_contract_failed"
fi

RUN_BODY="$(
  CONVERSATION_ID="$CONVERSATION_ID" RUN_ACTION="$RUN_ACTION" CANARY_LANGUAGE="$LANGUAGE" python3 - <<'PY'
import json
import os

print(json.dumps({
    "conversation_id": os.environ["CONVERSATION_ID"],
    "action": json.loads(os.environ["RUN_ACTION"]),
    "language": os.environ["CANARY_LANGUAGE"],
}))
PY
)"

if ! curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$RUN_BODY" \
  "${API_URL}/api/v1/chat/stream" > "$RUN_STREAM"; then
  handle_stream_failure "run"
fi

if ! RUN_RESULT="$(
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
)"; then
  fail_canary "run_stream" "run_contract_failed"
fi

BACKTEST_JOB_ID=""
poll_backtest_job() {
  local job_id="$1"
  local poll_deadline=$((SECONDS + TIMEOUT_SECONDS))
  local poll_result
  local job_label
  job_label="$(privacy_safe_id_label backtest_job "$job_id")"

  echo "Polling backtest job: $job_label"
  while true; do
    if ! curl -fsS \
      -b "$COOKIE_JAR" \
      "${API_URL}/api/v1/backtest-jobs/${job_id}" > "$JOB_RESPONSE"; then
      fail_canary "backtest_job" "backtest_job_fetch_failed"
    fi
    if ! poll_result="$(
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
    print(f"terminal:{status}")
else:
    print(f"pending:{status or 'unknown'}")
PY
    )"; then
      fail_canary "backtest_job" "backtest_job_parse_failed"
    fi
    case "$poll_result" in
      succeeded:*)
        BACKTEST_RUN_ID="${poll_result#succeeded:}"
        RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
        echo "OK: backtest job completed with run $RESULT_LABEL"
        return 0
        ;;
      terminal:*)
        echo "ERROR: backtest job ended unsuccessfully: $poll_result"
        print_safe_job_response
        fail_canary "backtest_job" "backtest_job_terminal"
        ;;
      pending:*)
        if [ "$SECONDS" -ge "$poll_deadline" ]; then
          echo "ERROR: backtest job did not complete within ${TIMEOUT_SECONDS}s"
          print_safe_job_response
          fail_canary "backtest_job" "backtest_job_timeout"
        fi
        echo "  waiting for backtest job... ${poll_result#pending:}"
        sleep "$POLL_SLEEP_SECONDS"
        ;;
      *)
        echo "ERROR: unknown backtest job poll result: $poll_result"
        print_safe_job_response
        fail_canary "backtest_job" "backtest_job_unknown_poll_result"
        ;;
    esac
  done
}

case "$RUN_RESULT" in
  job:*)
    BACKTEST_JOB_ID="${RUN_RESULT#job:}"
    BACKTEST_JOB_LABEL="$(privacy_safe_id_label backtest_job "$BACKTEST_JOB_ID")"
    RESULT_KIND="backtest_job"
    poll_backtest_job "$BACKTEST_JOB_ID"
    ;;
  run:*)
    BACKTEST_RUN_ID="${RUN_RESULT#run:}"
    RESULT_KIND="backtest_run"
    RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
    echo "OK: run stream returned immediate run $RESULT_LABEL"
    ;;
  *)
    echo "ERROR: unknown run stream result: $RUN_RESULT"
    fail_canary "run_stream" "unknown_run_stream_result"
    ;;
esac

if ! MESSAGES_JSON="$(fetch_conversation_messages)"; then
  fail_canary "reload_hydration" "message_fetch_failed"
fi
if ! assert_reload_hydration_payload true; then
  fail_canary "reload_hydration" "reload_hydration_contract_failed"
fi

if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  if ! BACKTEST_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/backtest_runs?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"; then
    fail_canary "supabase_verifier" "backtest_rows_fetch_failed"
  fi
  JOB_ROWS="[]"
  if [ -n "$BACKTEST_JOB_ID" ]; then
    if ! JOB_ROWS="$(
      curl -fsS \
        -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
        "${SUPABASE_URL}/rest/v1/backtest_jobs?select=id,status,result_run_id,execution_metadata&id=eq.${BACKTEST_JOB_ID}&limit=1"
    )"; then
      fail_canary "supabase_verifier" "job_rows_fetch_failed"
    fi
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
    if ! RECEIPT_ROWS="$(
      curl -fsS \
        -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
        "${SUPABASE_URL}/rest/v1/route_receipts?select=id&conversation_id=eq.${CONVERSATION_ID}&run_id=eq.${RESULT_RUN_ID}&task=eq.result_summary&limit=1"
    )"; then
      fail_canary "supabase_verifier" "receipt_rows_fetch_failed"
    fi
  fi
  if ! python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" "$JOB_ROWS" "$BACKTEST_JOB_ID" "$RESULT_RUN_ID" <<'PY'
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
  then
    fail_canary "supabase_verifier" "supabase_verifier_failed"
  fi
else
  echo "Skipping Supabase verifier; set ARGUS_CANARY_SUPABASE_URL and ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY to verify DB rows."
fi

CANARY_STATUS="passed"
write_canary_evidence

echo "Canary passed: confirmation, run_backtest action, async job/run result, LLM readout voice, and messages are present."

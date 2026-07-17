#!/bin/bash
# Browser-owned Golden Path canary for the private-alpha Render deployment.

set -euo pipefail
umask 077

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
LANGUAGE="${ARGUS_CANARY_LANGUAGE:-es-419}"
EXPECT_MODE="${ARGUS_CANARY_EXPECT_MODE:-${ARGUS_WARMUP_EXPECT_MODE:-real-workflow}}"
EVIDENCE_PATH="${ARGUS_CANARY_EVIDENCE_PATH:-}"
CAPTURE_PATH="${ARGUS_CANARY_CAPTURE_PATH:-}"
CANDIDATE_SHA="${ARGUS_CANARY_SHA:-${GITHUB_SHA:-}}"
CHECKED_OUT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
FOCUSED_SYMBOL_PATH="${ARGUS_CANARY_FOCUSED_SYMBOL_PATH:-}"
RELEASE_PROFILE_TOOL="$SCRIPT_DIR/private-alpha-release-profile.py"
PROMPT="$(python3 "$RELEASE_PROFILE_TOOL" canary-value prompt 2>/dev/null || true)"
DECISION_STATE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value decision_state 2>/dev/null || true)"
DECISION_NOTE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value decision_note 2>/dev/null || true)"
SEARCH_QUERY="$(python3 "$RELEASE_PROFILE_TOOL" canary-value search_query 2>/dev/null || true)"

if [ -z "$CHECKED_OUT_SHA" ]; then
  CHECKED_OUT_SHA="unknown"
fi
if [ -z "$CANDIDATE_SHA" ]; then
  CANDIDATE_SHA="$CHECKED_OUT_SHA"
fi

BROWSER_IDENTITY_HANDOFF="$(mktemp)"
COOKIE_JAR="$(mktemp)"
API_JOB_RESPONSE="$(mktemp)"
API_MESSAGES_RESPONSE="$(mktemp)"
API_SEARCH_RESPONSE="$(mktemp)"
CONVERSATION_ROWS="$(mktemp)"
JOB_ROWS="$(mktemp)"
RUN_ROWS="$(mktemp)"
EVIDENCE_ROWS="$(mktemp)"
DECISION_ROWS="$(mktemp)"
IDEA_ROWS="$(mktemp)"
IDEA_VERSION_ROWS="$(mktemp)"
RECEIPT_ROWS="$(mktemp)"
chmod 600 "$BROWSER_IDENTITY_HANDOFF"

cleanup() {
  rm -f "$BROWSER_IDENTITY_HANDOFF"
  rm -f \
    "$COOKIE_JAR" \
    "$API_JOB_RESPONSE" \
    "$API_MESSAGES_RESPONSE" \
    "$API_SEARCH_RESPONSE" \
    "$CONVERSATION_ROWS" \
    "$JOB_ROWS" \
    "$RUN_ROWS" \
    "$EVIDENCE_ROWS" \
    "$DECISION_ROWS" \
    "$IDEA_ROWS" \
    "$IDEA_VERSION_ROWS" \
    "$RECEIPT_ROWS"
}
trap cleanup EXIT

WARMUP_OUTPUT=""
API_DEPLOY_STATUS_OUTPUT=""
WEB_DEPLOY_STATUS_OUTPUT=""
WORKFLOW_VERSION_STATUS_OUTPUT=""
ENV_FINGERPRINT=""
RELEASE_PROFILE_HASH=""
WORKFLOW_ENV_FINGERPRINT=""
WORKFLOW_ENV_STATUS=""
WORKFLOW_RUNTIME_PROVIDER_MODE=""
WORKFLOW_RUNTIME_PROOF=""
WORKFLOW_TASK=""
REAL_WORKFLOW_TASK=""
API_DEPLOY_SHA=""
WEB_DEPLOY_SHA=""
API_DEPLOY_STATUS=""
WEB_DEPLOY_STATUS=""
WORKFLOW_VERSION_COMMIT=""
WORKFLOW_VERSION_ID=""
WORKFLOW_VERSION_STATUS=""
WORKFLOW_EXPECTED_VERSION_ID=""
USER_ID=""
CONVERSATION_ID=""
BACKTEST_JOB_ID=""
BACKTEST_RUN_ID=""
EVIDENCE_ARTIFACT_ID=""
DECISION_NOTE_ID=""
IDEA_ID=""
IDEA_VERSION_ID=""
CONVERSATION_LABEL=""
BACKTEST_JOB_LABEL=""
RESULT_LABEL=""
EVIDENCE_ARTIFACT_LABEL=""
DECISION_NOTE_LABEL=""
IDEA_LABEL=""
IDEA_VERSION_LABEL=""
BROWSER_CANARY_STATUS="not_run"
BROWSER_CONSOLE_ERROR_COUNT=""
BROWSER_PAGE_ERROR_COUNT=""
BROWSER_BLOCKING_OVERLAY_PRESENT=""
RUN_ACTION_REQUEST_COUNT=""
CANARY_STATUS="running"
CANARY_FAILURE_STAGE=""
CANARY_FAILURE_REASON=""

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

extract_warmup_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); found=1; exit } END { if (!found) exit 1 }' <<< "$WARMUP_OUTPUT"
}

extract_status_value() {
  local status="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); found=1; exit } END { if (!found) exit 1 }' <<< "$status"
}

build_release_evidence_json() {
  CANARY_STATUS="$CANARY_STATUS" \
  CANARY_FAILURE_STAGE="$CANARY_FAILURE_STAGE" \
  CANARY_FAILURE_REASON="$CANARY_FAILURE_REASON" \
  CANARY_EXPECTED_MODE="$EXPECT_MODE" \
  CANARY_RELEASE_PROFILE_HASH="$RELEASE_PROFILE_HASH" \
  CANARY_ENV_FINGERPRINT="$ENV_FINGERPRINT" \
  CANARY_WORKFLOW_ENV_FINGERPRINT="$WORKFLOW_ENV_FINGERPRINT" \
  CANARY_WORKFLOW_ENV_STATUS="$WORKFLOW_ENV_STATUS" \
  CANARY_WORKFLOW_RUNTIME_PROVIDER_MODE="$WORKFLOW_RUNTIME_PROVIDER_MODE" \
  CANARY_WORKFLOW_RUNTIME_PROOF="$WORKFLOW_RUNTIME_PROOF" \
  CANARY_WORKFLOW_TASK="$WORKFLOW_TASK" \
  CANARY_REAL_WORKFLOW_TASK="$REAL_WORKFLOW_TASK" \
  CANARY_API_DEPLOY_SHA="$API_DEPLOY_SHA" \
  CANARY_WEB_DEPLOY_SHA="$WEB_DEPLOY_SHA" \
  CANARY_API_DEPLOY_STATUS="$API_DEPLOY_STATUS" \
  CANARY_WEB_DEPLOY_STATUS="$WEB_DEPLOY_STATUS" \
  CANARY_WORKFLOW_VERSION_COMMIT="$WORKFLOW_VERSION_COMMIT" \
  CANARY_WORKFLOW_VERSION_ID="$WORKFLOW_VERSION_ID" \
  CANARY_WORKFLOW_VERSION_STATUS="$WORKFLOW_VERSION_STATUS" \
  CANARY_EXPECTED_SHA="$CANDIDATE_SHA" \
  CANARY_CHECKED_OUT_SHA="$CHECKED_OUT_SHA" \
  CANARY_LANGUAGE="$LANGUAGE" \
  CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH" \
  CANARY_CONVERSATION_LABEL="$CONVERSATION_LABEL" \
  CANARY_BACKTEST_JOB_LABEL="$BACKTEST_JOB_LABEL" \
  CANARY_RESULT_LABEL="$RESULT_LABEL" \
  CANARY_EVIDENCE_ARTIFACT_LABEL="$EVIDENCE_ARTIFACT_LABEL" \
  CANARY_DECISION_NOTE_LABEL="$DECISION_NOTE_LABEL" \
  CANARY_IDEA_LABEL="$IDEA_LABEL" \
  CANARY_IDEA_VERSION_LABEL="$IDEA_VERSION_LABEL" \
  CANARY_BROWSER_STATUS="$BROWSER_CANARY_STATUS" \
  CANARY_RUN_ACTION_REQUEST_COUNT="$RUN_ACTION_REQUEST_COUNT" \
  CANARY_BROWSER_CONSOLE_ERROR_COUNT="$BROWSER_CONSOLE_ERROR_COUNT" \
  CANARY_BROWSER_PAGE_ERROR_COUNT="$BROWSER_PAGE_ERROR_COUNT" \
  CANARY_BROWSER_BLOCKING_OVERLAY_PRESENT="$BROWSER_BLOCKING_OVERLAY_PRESENT" \
  python3 - <<'PY'
import json
import os

def optional(value: str):
    return value or None

def optional_int(value: str):
    return int(value) if value else None

payload = {
    "status": os.environ["CANARY_STATUS"],
    "failure_stage": optional(os.environ["CANARY_FAILURE_STAGE"]),
    "failure_reason": optional(os.environ["CANARY_FAILURE_REASON"]),
    "expected_mode": os.environ["CANARY_EXPECTED_MODE"],
    "release_profile_hash": optional(os.environ["CANARY_RELEASE_PROFILE_HASH"]),
    "env_fingerprint": optional(os.environ["CANARY_ENV_FINGERPRINT"]),
    "workflow_env_fingerprint": optional(os.environ["CANARY_WORKFLOW_ENV_FINGERPRINT"]),
    "workflow_env_status": optional(os.environ["CANARY_WORKFLOW_ENV_STATUS"]),
    "workflow_runtime_provider_mode": optional(os.environ["CANARY_WORKFLOW_RUNTIME_PROVIDER_MODE"]),
    "workflow_runtime_proof": optional(os.environ["CANARY_WORKFLOW_RUNTIME_PROOF"]),
    "workflow_task": optional(os.environ["CANARY_WORKFLOW_TASK"]),
    "real_workflow_task": optional(os.environ["CANARY_REAL_WORKFLOW_TASK"]),
    "api_deploy_sha": optional(os.environ["CANARY_API_DEPLOY_SHA"]),
    "web_deploy_sha": optional(os.environ["CANARY_WEB_DEPLOY_SHA"]),
    "api_deploy_status": optional(os.environ["CANARY_API_DEPLOY_STATUS"]),
    "web_deploy_status": optional(os.environ["CANARY_WEB_DEPLOY_STATUS"]),
    "workflow_version_commit": optional(os.environ["CANARY_WORKFLOW_VERSION_COMMIT"]),
    "workflow_version_id": optional(os.environ["CANARY_WORKFLOW_VERSION_ID"]),
    "workflow_version_status": optional(os.environ["CANARY_WORKFLOW_VERSION_STATUS"]),
    "candidate_sha": os.environ["CANARY_EXPECTED_SHA"],
    "checked_out_sha": os.environ["CANARY_CHECKED_OUT_SHA"],
    "language": os.environ["CANARY_LANGUAGE"],
    "focused_symbol_path": optional(os.environ["CANARY_FOCUSED_SYMBOL_PATH"]),
    "conversation_label": optional(os.environ["CANARY_CONVERSATION_LABEL"]),
    "backtest_job_label": optional(os.environ["CANARY_BACKTEST_JOB_LABEL"]),
    "result_label": optional(os.environ["CANARY_RESULT_LABEL"]),
    "evidence_artifact_label": optional(os.environ["CANARY_EVIDENCE_ARTIFACT_LABEL"]),
    "decision_note_label": optional(os.environ["CANARY_DECISION_NOTE_LABEL"]),
    "idea_label": optional(os.environ["CANARY_IDEA_LABEL"]),
    "idea_version_label": optional(os.environ["CANARY_IDEA_VERSION_LABEL"]),
    "browser_status": os.environ["CANARY_BROWSER_STATUS"],
    "run_action_request_count": optional_int(os.environ["CANARY_RUN_ACTION_REQUEST_COUNT"]),
    "browser_console_error_count": optional_int(os.environ["CANARY_BROWSER_CONSOLE_ERROR_COUNT"]),
    "browser_page_error_count": optional_int(os.environ["CANARY_BROWSER_PAGE_ERROR_COUNT"]),
    "browser_blocking_overlay_present": (
        os.environ["CANARY_BROWSER_BLOCKING_OVERLAY_PRESENT"] == "true"
        if os.environ["CANARY_BROWSER_BLOCKING_OVERLAY_PRESENT"]
        else None
    ),
    "privacy": "no_raw_ids; labels are sha256 prefixes",
}
print(json.dumps(payload, sort_keys=True))
PY
}

write_json_artifact() {
  local destination="$1"
  local artifact_kind="$2"
  if [ -z "$destination" ]; then
    return 0
  fi
  mkdir -p "$(dirname "$destination")"
  local evidence_json
  evidence_json="$(build_release_evidence_json)"
  CANARY_DESTINATION="$destination" \
  CANARY_ARTIFACT_KIND="$artifact_kind" \
  CANARY_EVIDENCE_JSON="$evidence_json" \
  CANARY_RAW_IDS="$USER_ID|$CONVERSATION_ID|$BACKTEST_JOB_ID|$BACKTEST_RUN_ID|$EVIDENCE_ARTIFACT_ID|$DECISION_NOTE_ID|$IDEA_ID|$IDEA_VERSION_ID" \
  python3 - <<'PY'
import json
import os
import pathlib

payload = json.loads(os.environ["CANARY_EVIDENCE_JSON"])
payload["artifact_kind"] = os.environ["CANARY_ARTIFACT_KIND"]
encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
for raw_id in os.environ["CANARY_RAW_IDS"].split("|"):
    if raw_id and raw_id in encoded:
        raise SystemExit("privacy-safe canary artifact contained a raw private identifier")
path = pathlib.Path(os.environ["CANARY_DESTINATION"])
path.write_text(encoded, encoding="utf-8")
path.chmod(0o600)
print(f"canary_{os.environ['CANARY_ARTIFACT_KIND']}_path={path}")
PY
}

write_canary_evidence() {
  write_json_artifact "$EVIDENCE_PATH" "evidence"
}

write_canary_capture() {
  if [ -z "$CAPTURE_PATH" ]; then
    return 0
  fi

  mkdir -p "$(dirname "$CAPTURE_PATH")"
  local exit_code=0
  local release_evidence_json
  release_evidence_json="$(build_release_evidence_json)"
  CANARY_CAPTURE_PATH="$CAPTURE_PATH" \
  CANARY_STATUS="$CANARY_STATUS" \
  CANARY_FAILURE_STAGE="$CANARY_FAILURE_STAGE" \
  CANARY_FAILURE_REASON="$CANARY_FAILURE_REASON" \
  CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH" \
  CANARY_RELEASE_EVIDENCE_JSON="$release_evidence_json" \
  CANARY_PROMPT="$PROMPT" \
  CANARY_CONVERSATION_LABEL="$CONVERSATION_LABEL" \
  CANARY_BACKTEST_JOB_LABEL="$BACKTEST_JOB_LABEL" \
  CANARY_RESULT_LABEL="$RESULT_LABEL" \
  CANARY_MESSAGES_FILE="$API_MESSAGES_RESPONSE" \
  CANARY_JOB_RESPONSE_FILE="$API_JOB_RESPONSE" \
  CANARY_RECEIPT_ROWS_FILE="$RECEIPT_ROWS" \
  python3 - <<'PY' || exit_code=$?
import json
import os
import pathlib
from typing import Any

from scripts.ops.canary_capture_sanitizer import (
    assert_sanitized_capture,
    sanitize_capture_value as sanitize,
)


def read_json_file(path: str) -> Any:
    if not path:
        return None
    file_path = pathlib.Path(path)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def first_dict(*values: Any) -> dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def extract_message_artifacts(messages_payload: Any) -> dict[str, Any]:
    artifacts: dict[str, Any] = {
        "message_artifacts": [],
        "result_card": None,
        "explanation_context": None,
        "final_response_payload": None,
        "confirmation_payload": None,
    }
    if not isinstance(messages_payload, dict):
        return artifacts
    items = messages_payload.get("items")
    if not isinstance(items, list):
        return artifacts
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        final_response_payload = metadata.get("final_response_payload")
        artifacts["message_artifacts"].append(
            {
                "role": item.get("role"),
                "metadata_keys": sorted(str(key) for key in metadata.keys()),
                "has_result_card": isinstance(metadata.get("result_card"), dict)
                or isinstance(metadata.get("conversation_result_card"), dict),
                "has_backtest_job": isinstance(metadata.get("backtest_job"), dict),
            }
        )
        if artifacts["result_card"] is None:
            artifacts["result_card"] = first_dict(
                metadata.get("result_card"),
                metadata.get("conversation_result_card"),
                (final_response_payload or {}).get("result_card")
                if isinstance(final_response_payload, dict)
                else None,
            )
        if artifacts["explanation_context"] is None:
            artifacts["explanation_context"] = first_dict(
                metadata.get("explanation_context"),
                (final_response_payload or {}).get("explanation_context")
                if isinstance(final_response_payload, dict)
                else None,
            )
        if artifacts["final_response_payload"] is None and isinstance(
            final_response_payload, dict
        ):
            artifacts["final_response_payload"] = final_response_payload
        if artifacts["confirmation_payload"] is None:
            artifacts["confirmation_payload"] = first_dict(
                metadata.get("confirmation_payload"),
                metadata.get("confirmation"),
            )
    return artifacts


def receipt_summary(receipt_payload: Any) -> dict[str, Any]:
    if not isinstance(receipt_payload, list):
        return {"status": "missing", "count": 0}
    tasks = sorted(
        {
            str(row.get("task"))
            for row in receipt_payload
            if isinstance(row, dict) and row.get("task")
        }
    )
    return {
        "status": "present" if receipt_payload else "missing",
        "count": len(receipt_payload),
        "tasks": tasks,
    }


messages_payload = read_json_file(os.environ["CANARY_MESSAGES_FILE"])
message_artifacts = extract_message_artifacts(messages_payload)
job_response = read_json_file(os.environ["CANARY_JOB_RESPONSE_FILE"])
receipt_payload = read_json_file(os.environ["CANARY_RECEIPT_ROWS_FILE"])
release = json.loads(os.environ["CANARY_RELEASE_EVIDENCE_JSON"])
final_response_payload = message_artifacts.get("final_response_payload")
job_run = job_response.get("run") if isinstance(job_response, dict) else None
result = first_dict(
    final_response_payload.get("result")
    if isinstance(final_response_payload, dict)
    else None,
    job_run,
)
launch_payload = {
    "language": release["language"],
    "message": os.environ["CANARY_PROMPT"],
    "focused_symbol_path": os.environ["CANARY_FOCUSED_SYMBOL_PATH"] or None,
    "confirmation_payload": message_artifacts.get("confirmation_payload"),
}
payload = {
    "schema_version": 1,
    "artifact_kind": "capture",
    "status": os.environ["CANARY_STATUS"],
    "failure": {
        "stage": os.environ["CANARY_FAILURE_STAGE"] or None,
        "reason": os.environ["CANARY_FAILURE_REASON"] or None,
        "status": os.environ["CANARY_STATUS"],
    },
    "release": release,
    "labels": {
        "conversation": os.environ["CANARY_CONVERSATION_LABEL"] or None,
        "backtest_job": os.environ["CANARY_BACKTEST_JOB_LABEL"] or None,
        "result": os.environ["CANARY_RESULT_LABEL"] or None,
    },
    "launch_payload": launch_payload,
    "result": result,
    "result_card": message_artifacts.get("result_card"),
    "explanation_context": message_artifacts.get("explanation_context"),
    "final_response_payload": message_artifacts.get("final_response_payload"),
    "message_artifacts": message_artifacts.get("message_artifacts", []),
    "job_response": job_response,
    "route_receipt": receipt_summary(receipt_payload),
    "privacy": "no_raw_ids; labels are sha256 prefixes; secrets redacted",
}

path = pathlib.Path(os.environ["CANARY_CAPTURE_PATH"])
sanitized_payload = sanitize(payload)
assert_sanitized_capture(sanitized_payload)
path.write_text(
    json.dumps(sanitized_payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
path.chmod(0o600)
print(f"canary_capture_path={path}")
PY
  return "$exit_code"
}

fail_canary() {
  CANARY_STATUS="failed"
  CANARY_FAILURE_STAGE="$1"
  CANARY_FAILURE_REASON="$2"
  echo "ERROR: canary failed at ${CANARY_FAILURE_STAGE}: ${CANARY_FAILURE_REASON}"
  write_canary_evidence || true
  write_canary_capture || true
  exit 1
}

run_deploy_status_probe() {
  if ! API_DEPLOY_STATUS_OUTPUT="$("$SCRIPT_DIR/render-env-sync.sh" api-deploy-status)"; then
    fail_canary "deploy_status" "api_deploy_status_failed"
  fi
  if ! WEB_DEPLOY_STATUS_OUTPUT="$("$SCRIPT_DIR/render-env-sync.sh" web-deploy-status)"; then
    fail_canary "deploy_status" "web_deploy_status_failed"
  fi
  if ! WORKFLOW_VERSION_STATUS_OUTPUT="$("$SCRIPT_DIR/render-env-sync.sh" workflow-version-status)"; then
    fail_canary "deploy_status" "workflow_version_status_failed"
  fi

  API_DEPLOY_SHA="$(extract_status_value "$API_DEPLOY_STATUS_OUTPUT" commit || true)"
  WEB_DEPLOY_SHA="$(extract_status_value "$WEB_DEPLOY_STATUS_OUTPUT" commit || true)"
  API_DEPLOY_STATUS="$(extract_status_value "$API_DEPLOY_STATUS_OUTPUT" status || true)"
  WEB_DEPLOY_STATUS="$(extract_status_value "$WEB_DEPLOY_STATUS_OUTPUT" status || true)"
  WORKFLOW_VERSION_ID="$(extract_status_value "$WORKFLOW_VERSION_STATUS_OUTPUT" workflow_version_id || true)"
  WORKFLOW_VERSION_STATUS="$(extract_status_value "$WORKFLOW_VERSION_STATUS_OUTPUT" status || true)"
  WORKFLOW_VERSION_COMMIT="$(extract_status_value "$WORKFLOW_VERSION_STATUS_OUTPUT" commit || true)"
  WORKFLOW_EXPECTED_VERSION_ID="$(extract_status_value "$WORKFLOW_VERSION_STATUS_OUTPUT" expected_workflow_version_id || true)"

  if [ "$API_DEPLOY_STATUS" != "live" ]; then
    fail_canary "deploy_status" "api_deploy_not_live"
  fi
  if [ "$WEB_DEPLOY_STATUS" != "live" ]; then
    fail_canary "deploy_status" "web_deploy_not_live"
  fi
  if [ "$API_DEPLOY_SHA" != "$CANDIDATE_SHA" ]; then
    fail_canary "deploy_status" "api_deploy_sha_mismatch"
  fi
  if [ "$WEB_DEPLOY_SHA" != "$CANDIDATE_SHA" ]; then
    fail_canary "deploy_status" "web_deploy_sha_mismatch"
  fi
  if [ "$WORKFLOW_VERSION_STATUS" != "ready" ]; then
    fail_canary "deploy_status" "workflow_version_not_ready"
  fi
  if [ "$WORKFLOW_VERSION_COMMIT" != "$CANDIDATE_SHA" ]; then
    fail_canary "deploy_status" "workflow_version_commit_mismatch"
  fi
  if [ -z "$WORKFLOW_VERSION_ID" ] || [ "$WORKFLOW_EXPECTED_VERSION_ID" != "$WORKFLOW_VERSION_ID" ]; then
    fail_canary "deploy_status" "workflow_version_id_mismatch"
  fi

  echo "canary_api_deploy_status=$API_DEPLOY_STATUS"
  echo "canary_web_deploy_status=$WEB_DEPLOY_STATUS"
  echo "canary_api_deploy_sha=$API_DEPLOY_SHA"
  echo "canary_web_deploy_sha=$WEB_DEPLOY_SHA"
  echo "canary_workflow_version_status=$WORKFLOW_VERSION_STATUS"
  echo "canary_workflow_version_commit=$WORKFLOW_VERSION_COMMIT"
  echo "canary_workflow_version_id=$WORKFLOW_VERSION_ID"
}

run_warmup_probe() {
  if ! WARMUP_OUTPUT="$(.github/warmup-render.sh --expect-mode "$EXPECT_MODE")"; then
    print_sanitized_warmup_output
    fail_canary "warmup" "warmup_probe_failed"
  fi
  print_sanitized_warmup_output
}

validate_release_evidence_contract() {
  if ! python3 "$RELEASE_PROFILE_TOOL" validate >/dev/null; then
    fail_canary "release_profile" "release_profile_invalid"
  fi
  RELEASE_PROFILE_HASH="$(python3 "$RELEASE_PROFILE_TOOL" hash)"
  local profile_language
  profile_language="$(python3 "$RELEASE_PROFILE_TOOL" canary-value language)"
  if [ "$LANGUAGE" != "$profile_language" ]; then
    fail_canary "release_profile" "canary_language_mismatch"
  fi
  if [ -z "$PROMPT" ] || [ -z "$DECISION_STATE" ] || [ -z "$SEARCH_QUERY" ]; then
    fail_canary "release_profile" "browser_journey_input_missing"
  fi
  if [ "$CANDIDATE_SHA" != "unknown" ] && [ "$CHECKED_OUT_SHA" != "unknown" ] && [ "$CANDIDATE_SHA" != "$CHECKED_OUT_SHA" ]; then
    echo "ERROR: canary commit mismatch"
    fail_canary "commit" "canary_commit_mismatch"
  fi

  run_deploy_status_probe
  run_warmup_probe

  ENV_FINGERPRINT="$(extract_warmup_value env_fingerprint || true)"
  WORKFLOW_ENV_FINGERPRINT="$(extract_warmup_value workflow_env_fingerprint || true)"
  WORKFLOW_ENV_STATUS="$(extract_warmup_value workflow_env_status || true)"
  WORKFLOW_RUNTIME_PROVIDER_MODE="$(extract_warmup_value workflow_runtime_provider_mode || true)"
  WORKFLOW_RUNTIME_PROOF="$(extract_warmup_value workflow_runtime_proof || true)"
  WORKFLOW_TASK="$(extract_warmup_value workflow_task || true)"
  REAL_WORKFLOW_TASK="$(extract_warmup_value real_workflow_task || true)"
  local warmup_profile_status
  local warmup_profile_hash
  warmup_profile_status="$(extract_warmup_value release_profile_status || true)"
  warmup_profile_hash="$(extract_warmup_value release_profile_hash || true)"

  if [ "$warmup_profile_status" != "ready" ] || [ "$warmup_profile_hash" != "$RELEASE_PROFILE_HASH" ]; then
    fail_canary "release_profile" "release_profile_hash_mismatch"
  fi
  if [[ ! "$ENV_FINGERPRINT" =~ ^[0-9a-f]{64}$ ]]; then
    fail_canary "warmup" "missing_env_fingerprint"
  fi
  if [[ ! "$WORKFLOW_ENV_FINGERPRINT" =~ ^[0-9a-f]{64}$ ]] || [ "$WORKFLOW_ENV_STATUS" != "ready" ]; then
    fail_canary "warmup" "workflow_env_drift"
  fi
  if [ "$WORKFLOW_RUNTIME_PROVIDER_MODE" != "live_provider" ] || [ "$WORKFLOW_RUNTIME_PROOF" != "ready" ]; then
    fail_canary "warmup" "workflow_runtime_proof_missing"
  fi
  if [ -z "$WORKFLOW_TASK" ] || [ -z "$REAL_WORKFLOW_TASK" ]; then
    fail_canary "warmup" "workflow_task_missing"
  fi

  echo "canary_expected_mode=$EXPECT_MODE"
  echo "canary_release_profile_hash=$RELEASE_PROFILE_HASH"
  echo "canary_env_fingerprint=$ENV_FINGERPRINT"
  echo "canary_workflow_env_fingerprint=$WORKFLOW_ENV_FINGERPRINT"
  echo "canary_workflow_env_status=$WORKFLOW_ENV_STATUS"
  echo "canary_workflow_runtime_provider_mode=$WORKFLOW_RUNTIME_PROVIDER_MODE"
  echo "canary_workflow_runtime_proof=$WORKFLOW_RUNTIME_PROOF"
  echo "canary_workflow_task=$WORKFLOW_TASK"
  echo "canary_real_workflow_task=$REAL_WORKFLOW_TASK"
  echo "canary_expected_sha=$CANDIDATE_SHA"
  echo "canary_checked_out_sha=$CHECKED_OUT_SHA"
}

run_browser_canary() {
  if ! ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF="$BROWSER_IDENTITY_HANDOFF" \
    "$SCRIPT_DIR/canary-browser.sh"; then
    BROWSER_CANARY_STATUS="failed"
    return 1
  fi
  BROWSER_CANARY_STATUS="passed"
}

verify_browser_identity_handoff() {
  local values
  if ! values="$(python3 - "$BROWSER_IDENTITY_HANDOFF" <<'PY'
import json
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
if not path.is_file() or not path.read_text(encoding="utf-8").strip():
    raise SystemExit("browser-owned identity handoff is missing")
if stat.S_IMODE(path.stat().st_mode) & 0o077:
    raise SystemExit("browser-owned identity handoff permissions are not private")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise SystemExit("browser-owned identity handoff is invalid") from exc
if payload.get("schema_version") != 1 or payload.get("source") != "playwright":
    raise SystemExit("browser-owned identity handoff contract is invalid")

keys = (
    "user_id",
    "conversation_id",
    "backtest_job_id",
    "backtest_run_id",
    "evidence_artifact_id",
    "decision_note_id",
    "idea_id",
    "idea_version_id",
)
values = []
for key in keys:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("browser-owned identity handoff omitted a required identity")
    values.append(value)
if payload.get("decision_state") not in {"watching", "promising", "rejected", "revisit_later"}:
    raise SystemExit("browser-owned identity handoff omitted the decision state")
if payload.get("run_action_request_count") != 1:
    raise SystemExit("browser-owned journey did not submit exactly one Run action")
assertions = payload.get("assertions")
if not isinstance(assertions, dict):
    raise SystemExit("browser-owned identity handoff omitted assertion evidence")
if assertions.get("result_rendered_once") is not True:
    raise SystemExit("browser-owned journey did not render exactly one completed result")
if assertions.get("reload_hydrated") is not True or assertions.get("omnisearch_reopened_source") is not True:
    raise SystemExit("browser-owned journey did not prove continuity")
if assertions.get("console_error_count") != 0 or assertions.get("page_error_count") != 0:
    raise SystemExit("browser-owned journey reported browser errors")
if assertions.get("blocking_overlay_present") is not False:
    raise SystemExit("browser-owned journey reported a blocking overlay")
values.extend(
    [
        payload["decision_state"],
        str(payload["run_action_request_count"]),
        str(assertions["console_error_count"]),
        str(assertions["page_error_count"]),
        str(assertions["blocking_overlay_present"]).lower(),
    ]
)
print("\t".join(values))
PY
  )"; then
    return 1
  fi

  IFS=$'\t' read -r \
    USER_ID \
    CONVERSATION_ID \
    BACKTEST_JOB_ID \
    BACKTEST_RUN_ID \
    EVIDENCE_ARTIFACT_ID \
    DECISION_NOTE_ID \
    IDEA_ID \
    IDEA_VERSION_ID \
    CAPTURED_DECISION_STATE \
    RUN_ACTION_REQUEST_COUNT \
    BROWSER_CONSOLE_ERROR_COUNT \
    BROWSER_PAGE_ERROR_COUNT \
    BROWSER_BLOCKING_OVERLAY_PRESENT <<< "$values"

  if [ "$CAPTURED_DECISION_STATE" != "$DECISION_STATE" ]; then
    return 1
  fi
  CONVERSATION_LABEL="$(privacy_safe_id_label conversation "$CONVERSATION_ID")"
  BACKTEST_JOB_LABEL="$(privacy_safe_id_label backtest_job "$BACKTEST_JOB_ID")"
  RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
  EVIDENCE_ARTIFACT_LABEL="$(privacy_safe_id_label evidence_artifact "$EVIDENCE_ARTIFACT_ID")"
  DECISION_NOTE_LABEL="$(privacy_safe_id_label decision_note "$DECISION_NOTE_ID")"
  IDEA_LABEL="$(privacy_safe_id_label idea "$IDEA_ID")"
  IDEA_VERSION_LABEL="$(privacy_safe_id_label idea_version "$IDEA_VERSION_ID")"
  echo "canary_browser_identity_handoff=verified"
  echo "canary_conversation=$CONVERSATION_LABEL"
  echo "canary_backtest_job=$BACKTEST_JOB_LABEL"
  echo "canary_result=$RESULT_LABEL"
}

recover_browser_failure_capture_inputs() {
  local values
  if ! values="$(python3 - "$BROWSER_IDENTITY_HANDOFF" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.is_file() or not path.read_text(encoding="utf-8").strip():
    raise SystemExit(1)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise SystemExit(1) from exc
if payload.get("schema_version") != 1 or payload.get("source") != "playwright":
    raise SystemExit(1)
required = ("user_id", "conversation_id")
if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
    raise SystemExit(1)
keys = (
    "user_id",
    "conversation_id",
    "backtest_job_id",
    "backtest_run_id",
    "evidence_artifact_id",
    "idea_id",
    "idea_version_id",
)
print("|".join(payload.get(key) if isinstance(payload.get(key), str) else "-" for key in keys))
PY
  )"; then
    return 0
  fi

  IFS='|' read -r \
    USER_ID \
    CONVERSATION_ID \
    BACKTEST_JOB_ID \
    BACKTEST_RUN_ID \
    EVIDENCE_ARTIFACT_ID \
    IDEA_ID \
    IDEA_VERSION_ID <<< "$values"
  [ "$BACKTEST_JOB_ID" = "-" ] && BACKTEST_JOB_ID=""
  [ "$BACKTEST_RUN_ID" = "-" ] && BACKTEST_RUN_ID=""
  [ "$EVIDENCE_ARTIFACT_ID" = "-" ] && EVIDENCE_ARTIFACT_ID=""
  [ "$IDEA_ID" = "-" ] && IDEA_ID=""
  [ "$IDEA_VERSION_ID" = "-" ] && IDEA_VERSION_ID=""

  CONVERSATION_LABEL="$(privacy_safe_id_label conversation "$CONVERSATION_ID")"
  BACKTEST_JOB_LABEL="$(privacy_safe_id_label backtest_job "$BACKTEST_JOB_ID")"
  RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
  EVIDENCE_ARTIFACT_LABEL="$(privacy_safe_id_label evidence_artifact "$EVIDENCE_ARTIFACT_ID")"
  IDEA_LABEL="$(privacy_safe_id_label idea "$IDEA_ID")"
  IDEA_VERSION_LABEL="$(privacy_safe_id_label idea_version "$IDEA_VERSION_ID")"

  if ! login_for_read_only_api_postconditions; then
    return 0
  fi
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages" \
    > "$API_MESSAGES_RESPONSE" || true
  if [ -z "$BACKTEST_JOB_ID" ]; then
    local recovered_job=""
    local attempt
    for attempt in 1 2 3 4 5; do
      if supabase_get \
        "${SUPABASE_URL}/rest/v1/backtest_jobs?select=id,result_run_id&conversation_id=eq.${CONVERSATION_ID}&user_id=eq.${USER_ID}&order=created_at.desc&limit=2" \
        "$JOB_ROWS"; then
        recovered_job="$(python3 - "$JOB_ROWS" <<'PY' || true
import json
import pathlib
import sys

rows = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(rows, list) or len(rows) != 1:
    raise SystemExit(1)
job = rows[0]
job_id = job.get("id")
run_id = job.get("result_run_id")
if not isinstance(job_id, str) or not job_id:
    raise SystemExit(1)
print(f"{job_id}|{run_id if isinstance(run_id, str) and run_id else '-'}")
PY
)"
      fi
      if [ -n "$recovered_job" ]; then
        IFS='|' read -r BACKTEST_JOB_ID BACKTEST_RUN_ID <<< "$recovered_job"
        [ "$BACKTEST_RUN_ID" = "-" ] && BACKTEST_RUN_ID=""
        BACKTEST_JOB_LABEL="$(privacy_safe_id_label backtest_job "$BACKTEST_JOB_ID")"
        RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
        break
      fi
      sleep 1
    done
  fi
  if [ -n "$BACKTEST_JOB_ID" ]; then
    curl -fsS -b "$COOKIE_JAR" \
      "${API_URL}/api/v1/backtest-jobs/${BACKTEST_JOB_ID}" \
      > "$API_JOB_RESPONSE" || true
    if [ -z "$BACKTEST_RUN_ID" ] && [ -s "$API_JOB_RESPONSE" ]; then
      BACKTEST_RUN_ID="$(python3 - "$API_JOB_RESPONSE" <<'PY' || true
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
job = payload.get("job") if isinstance(payload, dict) else None
run = payload.get("run") if isinstance(payload, dict) else None
run_id = job.get("result_run_id") if isinstance(job, dict) else None
if not isinstance(run_id, str) or not run_id:
    run_id = run.get("id") if isinstance(run, dict) else None
if isinstance(run_id, str) and run_id:
    print(run_id)
PY
)"
      RESULT_LABEL="$(privacy_safe_id_label backtest_run "$BACKTEST_RUN_ID")"
    fi
  fi
  if [ -n "$BACKTEST_RUN_ID" ]; then
    supabase_get \
      "${SUPABASE_URL}/rest/v1/route_receipts?select=id,user_id,conversation_id,run_id,task,outcome&conversation_id=eq.${CONVERSATION_ID}&run_id=eq.${BACKTEST_RUN_ID}" \
      "$RECEIPT_ROWS" || true
  fi
  echo "canary_failed_browser_capture_inputs=collected"
}

login_for_read_only_api_postconditions() {
  local login_body
  login_body="$(CANARY_EMAIL="$EMAIL" CANARY_PASSWORD="$PASSWORD" python3 - <<'PY'
import json
import os
print(json.dumps({"email": os.environ["CANARY_EMAIL"], "password": os.environ["CANARY_PASSWORD"]}))
PY
  )"
  curl -fsS \
    -c "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "$login_body" \
    "${API_URL}/api/v1/auth/login" >/dev/null
}

verify_api_postconditions() {
  local encoded_search_query
  encoded_search_query="$(CANARY_SEARCH_QUERY="$SEARCH_QUERY" python3 - <<'PY'
import os
import urllib.parse
print(urllib.parse.quote(os.environ["CANARY_SEARCH_QUERY"], safe=""))
PY
  )"
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/backtest-jobs/${BACKTEST_JOB_ID}" > "$API_JOB_RESPONSE"
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages" > "$API_MESSAGES_RESPONSE"
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/search?q=${encoded_search_query}&include_ledger_groups=true" > "$API_SEARCH_RESPONSE"

  CANARY_JOB_FILE="$API_JOB_RESPONSE" \
  CANARY_MESSAGES_FILE="$API_MESSAGES_RESPONSE" \
  CANARY_SEARCH_FILE="$API_SEARCH_RESPONSE" \
  CANARY_CONVERSATION_ID="$CONVERSATION_ID" \
  CANARY_JOB_ID="$BACKTEST_JOB_ID" \
  CANARY_RUN_ID="$BACKTEST_RUN_ID" \
  CANARY_EVIDENCE_ID="$EVIDENCE_ARTIFACT_ID" \
  CANARY_DECISION_ID="$DECISION_NOTE_ID" \
  CANARY_DECISION_STATE="$DECISION_STATE" \
  CANARY_IDEA_ID="$IDEA_ID" \
  CANARY_IDEA_VERSION_ID="$IDEA_VERSION_ID" \
  CANARY_FOCUSED_SYMBOL_PATH="$FOCUSED_SYMBOL_PATH" \
  python3 - <<'PY'
import json
import os
import pathlib

def load(name: str):
    return json.loads(pathlib.Path(os.environ[name]).read_text(encoding="utf-8"))

job_payload = load("CANARY_JOB_FILE")
job = job_payload.get("job")
run = job_payload.get("run")
if not isinstance(job, dict) or not isinstance(run, dict):
    raise SystemExit("read-only job API omitted finalized records")
if (
    job.get("id") != os.environ["CANARY_JOB_ID"]
    or job.get("conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or job.get("status") != "succeeded"
    or job.get("result_run_id") != os.environ["CANARY_RUN_ID"]
    or run.get("id") != os.environ["CANARY_RUN_ID"]
    or run.get("conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or run.get("status") != "completed"
):
    raise SystemExit("read-only job API identity did not match browser capture")
card = run.get("conversation_result_card")
if not isinstance(card, dict):
    raise SystemExit("read-only job API omitted the result card")
expected_card = {
    "evidence_artifact_id": os.environ["CANARY_EVIDENCE_ID"],
    "decision_note_id": os.environ["CANARY_DECISION_ID"],
    "decision_state": os.environ["CANARY_DECISION_STATE"],
    "idea_id": os.environ["CANARY_IDEA_ID"],
    "idea_version_id": os.environ["CANARY_IDEA_VERSION_ID"],
}
if any(card.get(key) != value for key, value in expected_card.items()):
    raise SystemExit("read-only job API result card identity is incomplete")

expected_symbols = {
    symbol.strip().upper()
    for symbol in os.environ["CANARY_FOCUSED_SYMBOL_PATH"].split(",")
    if symbol.strip()
}
actual_symbols = {
    str(symbol).strip().upper()
    for symbol in run.get("symbols", [])
    if isinstance(symbol, str) and symbol.strip()
}
if expected_symbols and not expected_symbols.issubset(actual_symbols):
    raise SystemExit("read-only job API focused symbol path is incomplete")

messages = load("CANARY_MESSAGES_FILE")
items = messages.get("items") if isinstance(messages, dict) else None
if not isinstance(items, list) or len(items) < 2:
    raise SystemExit("read-only messages API omitted Golden Path history")
encoded_messages = json.dumps(items, sort_keys=True)
for required_identity in (
    os.environ["CANARY_RUN_ID"],
    os.environ["CANARY_EVIDENCE_ID"],
    os.environ["CANARY_DECISION_ID"],
):
    if required_identity not in encoded_messages:
        raise SystemExit("read-only messages API omitted canonical result continuity")

search = load("CANARY_SEARCH_FILE")
search_items = search.get("items") if isinstance(search, dict) else None
if not isinstance(search_items, list):
    raise SystemExit("read-only Omnisearch API omitted items")
for item in search_items:
    if not isinstance(item, dict):
        continue
    if item.get("type") == "evidence" and item.get("id") == os.environ["CANARY_EVIDENCE_ID"]:
        if (
            item.get("conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
            or item.get("lifecycle") != "decided"
        ):
            raise SystemExit("read-only Omnisearch API returned contradictory evidence")
        break
else:
    raise SystemExit("read-only Omnisearch API omitted browser-created evidence")
ledger_groups = search.get("ledger_groups")
if not isinstance(ledger_groups, list) or not any(
    isinstance(group, dict)
    and group.get("decision_state") == os.environ["CANARY_DECISION_STATE"]
    and isinstance(group.get("count"), int)
    and group["count"] >= 1
    for group in ledger_groups
):
    raise SystemExit("read-only Omnisearch API omitted the saved decision group")
PY
}

supabase_get() {
  local url="$1"
  local output_path="$2"
  curl -fsS \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    "$url" > "$output_path"
}

verify_canonical_postconditions() {
  supabase_get \
    "${SUPABASE_URL}/rest/v1/conversations?select=id,user_id&id=eq.${CONVERSATION_ID}" \
    "$CONVERSATION_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/backtest_jobs?select=id,user_id,conversation_id,status,result_run_id,execution_metadata&conversation_id=eq.${CONVERSATION_ID}" \
    "$JOB_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/backtest_runs?select=id,user_id,conversation_id,status,conversation_result_card&conversation_id=eq.${CONVERSATION_ID}" \
    "$RUN_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/evidence_artifacts?select=id,user_id,idea_id,idea_version_id,source_conversation_id,source_run_id,artifact_type,lifecycle&id=eq.${EVIDENCE_ARTIFACT_ID}" \
    "$EVIDENCE_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/decision_notes?select=id,user_id,evidence_artifact_id,idea_id,idea_version_id,source_conversation_id,decision_state,note&id=eq.${DECISION_NOTE_ID}" \
    "$DECISION_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/ideas?select=id,user_id,source_conversation_id,active_version_id,lifecycle&id=eq.${IDEA_ID}" \
    "$IDEA_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/idea_versions?select=id,user_id,idea_id,source_conversation_id,source_run_id,lifecycle&id=eq.${IDEA_VERSION_ID}" \
    "$IDEA_VERSION_ROWS"
  supabase_get \
    "${SUPABASE_URL}/rest/v1/route_receipts?select=id,user_id,conversation_id,run_id,task,outcome&conversation_id=eq.${CONVERSATION_ID}&run_id=eq.${BACKTEST_RUN_ID}&task=eq.result_summary" \
    "$RECEIPT_ROWS"

  CANARY_CONVERSATION_ROWS="$CONVERSATION_ROWS" \
  CANARY_JOB_ROWS="$JOB_ROWS" \
  CANARY_RUN_ROWS="$RUN_ROWS" \
  CANARY_EVIDENCE_ROWS="$EVIDENCE_ROWS" \
  CANARY_DECISION_ROWS="$DECISION_ROWS" \
  CANARY_IDEA_ROWS="$IDEA_ROWS" \
  CANARY_IDEA_VERSION_ROWS="$IDEA_VERSION_ROWS" \
  CANARY_RECEIPT_ROWS="$RECEIPT_ROWS" \
  CANARY_USER_ID="$USER_ID" \
  CANARY_CONVERSATION_ID="$CONVERSATION_ID" \
  CANARY_JOB_ID="$BACKTEST_JOB_ID" \
  CANARY_RUN_ID="$BACKTEST_RUN_ID" \
  CANARY_EVIDENCE_ID="$EVIDENCE_ARTIFACT_ID" \
  CANARY_DECISION_ID="$DECISION_NOTE_ID" \
  CANARY_DECISION_STATE="$DECISION_STATE" \
  CANARY_DECISION_NOTE="$DECISION_NOTE" \
  CANARY_IDEA_ID="$IDEA_ID" \
  CANARY_IDEA_VERSION_ID="$IDEA_VERSION_ID" \
  python3 - <<'PY'
import json
import os
import pathlib

def rows(name: str):
    value = json.loads(pathlib.Path(os.environ[name]).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit("Supabase postcondition response was not a row list")
    return value

conversation_rows = rows("CANARY_CONVERSATION_ROWS")
job_rows = rows("CANARY_JOB_ROWS")
run_rows = rows("CANARY_RUN_ROWS")
evidence_rows = rows("CANARY_EVIDENCE_ROWS")
decision_rows = rows("CANARY_DECISION_ROWS")
idea_rows = rows("CANARY_IDEA_ROWS")
idea_version_rows = rows("CANARY_IDEA_VERSION_ROWS")
receipt_rows = rows("CANARY_RECEIPT_ROWS")

if len(job_rows) != 1:
    raise SystemExit("expected exactly one canary backtest_job")
if len(run_rows) != 1:
    raise SystemExit("expected exactly one canary backtest_run")
for name, value in (
    ("conversation", conversation_rows),
    ("evidence", evidence_rows),
    ("decision", decision_rows),
    ("idea", idea_rows),
    ("idea version", idea_version_rows),
):
    if len(value) != 1:
        raise SystemExit(f"expected exactly one canonical {name} row")

user_id = os.environ["CANARY_USER_ID"]
all_owned_rows = (
    conversation_rows
    + job_rows
    + run_rows
    + evidence_rows
    + decision_rows
    + idea_rows
    + idea_version_rows
    + receipt_rows
)
if any(row.get("user_id") != user_id for row in all_owned_rows):
    raise SystemExit("canonical postcondition ownership mismatch")

conversation = conversation_rows[0]
job = job_rows[0]
run = run_rows[0]
evidence = evidence_rows[0]
decision = decision_rows[0]
idea = idea_rows[0]
idea_version = idea_version_rows[0]
if conversation.get("id") != os.environ["CANARY_CONVERSATION_ID"]:
    raise SystemExit("canonical conversation identity mismatch")
if (
    job.get("id") != os.environ["CANARY_JOB_ID"]
    or job.get("conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or job.get("status") != "succeeded"
    or job.get("result_run_id") != os.environ["CANARY_RUN_ID"]
):
    raise SystemExit("canonical job finalization mismatch")
workflow_metadata = (job.get("execution_metadata") or {}).get("workflow_backtest")
if not isinstance(workflow_metadata, dict):
    raise SystemExit("canonical job omitted workflow execution metadata")
if (
    workflow_metadata.get("result_readout_source") != "llm_explain_stage"
    or workflow_metadata.get("result_readout_fallback_used") is not False
):
    raise SystemExit("canonical job did not preserve LLM result voice")
if (
    run.get("id") != os.environ["CANARY_RUN_ID"]
    or run.get("conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or run.get("status") != "completed"
):
    raise SystemExit("canonical run finalization mismatch")
card = run.get("conversation_result_card")
if not isinstance(card, dict):
    raise SystemExit("canonical run omitted result card")
expected_card = {
    "idea_id": os.environ["CANARY_IDEA_ID"],
    "idea_version_id": os.environ["CANARY_IDEA_VERSION_ID"],
    "evidence_artifact_id": os.environ["CANARY_EVIDENCE_ID"],
    "decision_note_id": os.environ["CANARY_DECISION_ID"],
    "decision_state": os.environ["CANARY_DECISION_STATE"],
}
if any(card.get(key) != value for key, value in expected_card.items()):
    raise SystemExit("canonical result card identity mismatch")
if (
    evidence.get("id") != os.environ["CANARY_EVIDENCE_ID"]
    or evidence.get("idea_id") != os.environ["CANARY_IDEA_ID"]
    or evidence.get("idea_version_id") != os.environ["CANARY_IDEA_VERSION_ID"]
    or evidence.get("source_conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or evidence.get("source_run_id") != os.environ["CANARY_RUN_ID"]
    or evidence.get("artifact_type") != "backtest"
    or evidence.get("lifecycle") != "decided"
):
    raise SystemExit("canonical evidence identity mismatch")
if (
    decision.get("id") != os.environ["CANARY_DECISION_ID"]
    or decision.get("evidence_artifact_id") != os.environ["CANARY_EVIDENCE_ID"]
    or decision.get("idea_id") != os.environ["CANARY_IDEA_ID"]
    or decision.get("idea_version_id") != os.environ["CANARY_IDEA_VERSION_ID"]
    or decision.get("source_conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or decision.get("decision_state") != os.environ["CANARY_DECISION_STATE"]
    or decision.get("note") != os.environ["CANARY_DECISION_NOTE"]
):
    raise SystemExit("canonical decision identity mismatch")
if (
    idea.get("id") != os.environ["CANARY_IDEA_ID"]
    or idea.get("source_conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or idea.get("active_version_id") != os.environ["CANARY_IDEA_VERSION_ID"]
    or idea.get("lifecycle") != "decided"
):
    raise SystemExit("canonical idea identity mismatch")
if (
    idea_version.get("id") != os.environ["CANARY_IDEA_VERSION_ID"]
    or idea_version.get("idea_id") != os.environ["CANARY_IDEA_ID"]
    or idea_version.get("source_conversation_id") != os.environ["CANARY_CONVERSATION_ID"]
    or idea_version.get("source_run_id") != os.environ["CANARY_RUN_ID"]
    or idea_version.get("lifecycle") != "decided"
):
    raise SystemExit("canonical idea version identity mismatch")
if not any(row.get("task") == "result_summary" for row in receipt_rows):
    raise SystemExit("canonical result_summary route receipt is missing")
PY
}

if [ -z "$EMAIL" ]; then
  fail_canary "auth" "missing_canary_email"
fi
if [ -z "$PASSWORD" ]; then
  fail_canary "auth" "missing_canary_password"
fi
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  fail_canary "supabase_verifier" "missing_supabase_verifier_credentials"
fi

validate_release_evidence_contract

if ! run_browser_canary; then
  recover_browser_failure_capture_inputs || true
  fail_canary "browser" "rendered_golden_path_failed"
fi
if ! verify_browser_identity_handoff; then
  fail_canary "browser_identity" "private_identity_handoff_failed"
fi
if ! login_for_read_only_api_postconditions; then
  fail_canary "api_postconditions" "read_only_login_failed"
fi
if ! verify_api_postconditions; then
  fail_canary "api_postconditions" "canonical_api_postconditions_failed"
fi
if ! verify_canonical_postconditions; then
  fail_canary "supabase_postconditions" "canonical_supabase_postconditions_failed"
fi

CANARY_STATUS="passed"
write_canary_evidence
write_canary_capture
echo "Canary passed: the rendered Spanish browser owned one real Golden Path and all canonical postconditions matched."

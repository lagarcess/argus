#!/bin/bash
# Warm Render free services before a private-alpha tester session.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/argus-env.sh"
argus_load_root_env >/dev/null || true

usage() {
  cat <<'USAGE'
Usage:
  .github/warmup-render.sh [--expect-mode <safe-off|proof-shadow|real-workflow>]

Options:
  --expect-mode  Verify argus-api workflow flags without mutating Render config.
USAGE
}

EXPECTED_MODE="${ARGUS_WARMUP_EXPECT_MODE:-}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --expect-mode)
      EXPECTED_MODE="${2:-}"
      if [ -z "$EXPECTED_MODE" ]; then
        echo "--expect-mode requires a value."
        usage
        exit 2
      fi
      shift 2
      ;;
    help|-h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

APP_URL="${ARGUS_WARMUP_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"
API_URL="${ARGUS_WARMUP_API_URL:-$ARGUS_PRIVATE_LAUNCH_API_URL}"
OPS_TOKEN="${ARGUS_OPS_TOKEN:-}"
TIMEOUT_SECONDS="${ARGUS_WARMUP_TIMEOUT_SECONDS:-180}"
SLEEP_SECONDS="${ARGUS_WARMUP_SLEEP_SECONDS:-5}"

deadline=$((SECONDS + TIMEOUT_SECONDS))

wait_for_url() {
  local label="$1"
  local url="$2"
  shift 2
  local attempt=1

  echo "Warming $label: $url"
  while true; do
    if curl -fsS --max-time 15 "$@" "$url" > /dev/null; then
      echo "OK: $label responded"
      return 0
    fi

    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "ERROR: $label did not respond within ${TIMEOUT_SECONDS}s"
      return 1
    fi

    echo "  waiting for $label... attempt $attempt"
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done
}

wait_for_readiness() {
  if [ -z "$OPS_TOKEN" ]; then
    echo "ARGUS_OPS_TOKEN is required for product readiness warmup."
    return 1
  fi

  wait_for_url \
    "product readiness" \
    "${API_URL}/internal/readiness?force=true" \
    -H "Authorization: Bearer ${OPS_TOKEN}"
}

require_status_line() {
  local status="$1"
  local expected="$2"

  if ! grep -Fxq "$expected" <<< "$status"; then
    echo "ERROR: expected API mode line: $expected"
    return 1
  fi
}

assert_api_mode() {
  local mode="$1"
  local status

  if [ -z "$mode" ]; then
    return 0
  fi

  case "$mode" in
    safe-off|proof-shadow|real-workflow)
      ;;
    *)
      echo "Unknown expected API mode: $mode"
      usage
      return 2
      ;;
  esac

  echo "Checking API mode: $mode"
  status="$("$SCRIPT_DIR/render-env-sync.sh" api-status)"
  printf "%s\n" "$status"

  case "$mode" in
    safe-off)
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=false"
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=false"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof"
      require_status_line "$status" "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job"
      require_status_line "$status" "RENDER_API_KEY=<missing-or-empty>"
      ;;
    proof-shadow)
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true"
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=true"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof"
      require_status_line "$status" "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job"
      require_status_line "$status" "RENDER_API_KEY=<redacted-present>"
      ;;
    real-workflow)
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true"
      require_status_line "$status" "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=true"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true"
      require_status_line "$status" "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof"
      require_status_line "$status" "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job"
      require_status_line "$status" "RENDER_API_KEY=<redacted-present>"
      ;;
  esac

  echo "OK: API mode matched $mode"
}

echo "Argus private-launch warmup"
echo "Timeout: ${TIMEOUT_SECONDS}s"
echo ""

wait_for_url "API health" "${API_URL}/health"
wait_for_readiness
wait_for_url "frontend" "$APP_URL"
assert_api_mode "$EXPECTED_MODE"

echo ""
echo "Argus product path is ready for testers."

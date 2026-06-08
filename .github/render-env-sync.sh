#!/bin/bash
# Sync selected Argus env vars to Render without printing secret values.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/argus-env.sh"
argus_load_root_env >/dev/null || true

API_SERVICE_ID="${ARGUS_RENDER_API_SERVICE_ID:-$ARGUS_PRIVATE_LAUNCH_API_SERVICE_ID}"
WORKFLOW_SERVICE_ID="${ARGUS_RENDER_WORKFLOW_SERVICE_ID:-$ARGUS_RENDER_BACKTESTS_WORKFLOW_ID}"

usage() {
  cat <<'USAGE'
Usage:
  .github/render-env-sync.sh api-status
  .github/render-env-sync.sh api-safe-off
  .github/render-env-sync.sh api-proof-shadow-on
  .github/render-env-sync.sh api-real-workflow-on
  .github/render-env-sync.sh api-runtime
  .github/render-env-sync.sh workflow-proof
  .github/render-env-sync.sh workflow-release [commit]
  .github/render-env-sync.sh workflow-runtime

Commands:
  api-status              Print redacted API workflow env status for argus-api.
  api-safe-off            Disable API job dispatch/execution and blank its Render key.
  api-proof-shadow-on     Enable proof-only shadow dispatch to workflow_proof.
  api-real-workflow-on    Enable real async dispatch to run_backtest_job.
  api-runtime             Sync argus-api build/start commands and Poetry pin.
  workflow-proof          Sync workflow DB/task/provider env vars on argus-backtests.
  workflow-release        Release argus-backtests so env/build changes reach new runs.
  workflow-runtime        Sync workflow build/start commands on argus-backtests.

Compatibility aliases:
  api-dispatch-on   Alias for api-proof-shadow-on.
  api-dispatch-off  Alias for api-safe-off.

Required local env:
  RENDER_API_KEY

Additional local env for workflow-proof:
  ARGUS_WORKFLOW_DATABASE_URL or SUPABASE_POSTGRES_TRANSACTION_POOLER_URL
  ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS (optional; defaults to 300)
  ALPACA_API_KEY
  ALPACA_SECRET_KEY
  OPENROUTER_API_KEY
  ARGUS_UTILITY_MODEL
  ARGUS_UTILITY_FALLBACK_MODEL
  ARGUS_CHAT_MODEL
  ARGUS_CHAT_FALLBACK_MODEL
  ARGUS_STRUCTURED_MODEL
  ARGUS_STRUCTURED_FALLBACK_MODEL
  ARGUS_CONTEXT_MODEL
  ARGUS_CONTEXT_FALLBACK_MODEL
USAGE
}

require_local_env() {
  local name="$1"
  argus_require_env "$name"
}

put_render_env() {
  local service_id="$1"
  local key="$2"
  local value="$3"

  curl -fsS \
    --request PUT \
    --url "https://api.render.com/v1/services/${service_id}/env-vars/${key}" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json" \
    --header "Content-Type: application/json" \
    --data "$(jq -nc --arg value "$value" '{value: $value}')" \
    >/dev/null

  echo "synced ${service_id}:${key}"
}

delete_render_env() {
  local service_id="$1"
  local key="$2"
  local status

  status="$(
    curl -sS \
      -o /dev/null \
      -w "%{http_code}" \
      --request DELETE \
      --url "https://api.render.com/v1/services/${service_id}/env-vars/${key}" \
      --header "Authorization: Bearer ${RENDER_API_KEY}" \
      --header "Accept: application/json"
  )"

  if [ "$status" = "404" ]; then
    echo "already absent ${service_id}:${key}"
    return
  fi

  if [[ "$status" != 2* ]]; then
    echo "failed to delete ${service_id}:${key} (HTTP ${status})"
    exit 1
  fi

  echo "deleted ${service_id}:${key}"
}

render_env_json() {
  local service_id="$1"

  curl -fsS \
    --request GET \
    --url "https://api.render.com/v1/services/${service_id}/env-vars" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json"
}

render_workflow_json() {
  curl -fsS \
    --request GET \
    --url "https://api.render.com/v1/workflows/${WORKFLOW_SERVICE_ID}" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json"
}

print_api_status() {
  require_local_env RENDER_API_KEY
  render_env_json "$API_SERVICE_ID" | jq -r '
    [
      "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED",
      "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED",
      "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED",
      "ARGUS_BACKTEST_WORKFLOW_TASK",
      "ARGUS_BACKTEST_REAL_WORKFLOW_TASK",
      "ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT",
      "ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT",
      "ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT",
      "ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT",
      "RENDER_API_KEY"
    ] as $keys
    | [ .[]?.envVar? ] as $vars
    | $keys[]
    | . as $key
    | ($vars | map(select(.key == $key)) | .[0].value // null) as $value
    | if $key == "RENDER_API_KEY" then
        "\($key)=\(if ($value // "") == "" then "<missing-or-empty>" else "<redacted-present>" end)"
      else
        "\($key)=\($value // "<missing>")"
      end
  ' | sort
}

sync_api_proof_shadow_on() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_REAL_WORKFLOW_TASK "$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT "${ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT:-1}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT "${ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT:-2}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT "${ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT:-5}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT "${ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT:-10}"
  put_render_env "$API_SERVICE_ID" RENDER_API_KEY "$RENDER_API_KEY"
}

sync_api_real_workflow_on() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_REAL_WORKFLOW_TASK "$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT "${ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT:-1}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT "${ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT:-2}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT "${ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT:-5}"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT "${ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT:-10}"
  put_render_env "$API_SERVICE_ID" RENDER_API_KEY "$RENDER_API_KEY"
}

sync_api_safe_off() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_REAL_WORKFLOW_TASK "$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"
  delete_render_env "$API_SERVICE_ID" RENDER_API_KEY
}

sync_api_runtime() {
  require_local_env RENDER_API_KEY
  local update_payload

  update_payload="$(
    jq -nc \
      --arg build_command "$ARGUS_RENDER_API_BUILD_COMMAND" \
      --arg start_command "$ARGUS_RENDER_API_START_COMMAND" \
      '{
        serviceDetails: {
          envSpecificDetails: {
            buildCommand: $build_command,
            startCommand: $start_command
          },
          healthCheckPath: "/health"
        }
      }'
  )"

  curl -fsS \
    --request PATCH \
    --url "https://api.render.com/v1/services/${API_SERVICE_ID}" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json" \
    --header "Content-Type: application/json" \
    --data "$update_payload" \
    >/dev/null
  echo "synced ${API_SERVICE_ID}:api-runtime"
  put_render_env "$API_SERVICE_ID" POETRY_VERSION "$ARGUS_RENDER_POETRY_VERSION"
}

sync_workflow_proof() {
  require_local_env RENDER_API_KEY
  require_local_env ALPACA_API_KEY
  require_local_env ALPACA_SECRET_KEY
  require_local_env OPENROUTER_API_KEY
  require_local_env ARGUS_UTILITY_MODEL
  require_local_env ARGUS_UTILITY_FALLBACK_MODEL
  require_local_env ARGUS_CHAT_MODEL
  require_local_env ARGUS_CHAT_FALLBACK_MODEL
  require_local_env ARGUS_STRUCTURED_MODEL
  require_local_env ARGUS_STRUCTURED_FALLBACK_MODEL
  require_local_env ARGUS_CONTEXT_MODEL
  require_local_env ARGUS_CONTEXT_FALLBACK_MODEL
  local workflow_database_url="${ARGUS_WORKFLOW_DATABASE_URL:-${SUPABASE_POSTGRES_TRANSACTION_POOLER_URL:-}}"
  if [ -z "$workflow_database_url" ] || [[ "$workflow_database_url" == YOUR_* ]] || [[ "$workflow_database_url" == your_* ]]; then
    echo "ARGUS_WORKFLOW_DATABASE_URL or SUPABASE_POSTGRES_TRANSACTION_POOLER_URL is required."
    exit 1
  fi

  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_WORKFLOW_DATABASE_URL "$workflow_database_url"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_RENDER_WORKFLOW_PROOF_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_WORKFLOW_PROOF_PLAN "${ARGUS_WORKFLOW_PROOF_PLAN:-starter}"
  put_render_env "$WORKFLOW_SERVICE_ID" POETRY_VERSION "$ARGUS_RENDER_POETRY_VERSION"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS "${ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS:-300}"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_MARKET_DATA_PROVIDER_MODE "${ARGUS_MARKET_DATA_PROVIDER_MODE:-live_provider}"
  put_render_env "$WORKFLOW_SERVICE_ID" ENABLE_MARKET_DATA_CACHE "${ENABLE_MARKET_DATA_CACHE:-false}"
  put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_API_KEY "$ALPACA_API_KEY"
  put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_SECRET_KEY "$ALPACA_SECRET_KEY"
  put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_PAPER_TRADING "${ALPACA_PAPER_TRADING:-true}"
  put_render_env "$WORKFLOW_SERVICE_ID" OPENROUTER_API_KEY "$OPENROUTER_API_KEY"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_UTILITY_MODEL "$ARGUS_UTILITY_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_UTILITY_FALLBACK_MODEL "$ARGUS_UTILITY_FALLBACK_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_CHAT_MODEL "$ARGUS_CHAT_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_CHAT_FALLBACK_MODEL "$ARGUS_CHAT_FALLBACK_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS "${ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS:-20}"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_STRUCTURED_MODEL "$ARGUS_STRUCTURED_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_STRUCTURED_FALLBACK_MODEL "$ARGUS_STRUCTURED_FALLBACK_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_CONTEXT_MODEL "$ARGUS_CONTEXT_MODEL"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_CONTEXT_FALLBACK_MODEL "$ARGUS_CONTEXT_FALLBACK_MODEL"
}

sync_workflow_runtime() {
  require_local_env RENDER_API_KEY
  local current_workflow
  local update_payload

  current_workflow="$(render_workflow_json)"
  update_payload="$(
    jq -nc \
      --argjson workflow "$current_workflow" \
      --arg build_command "$ARGUS_RENDER_WORKFLOW_BUILD_COMMAND" \
      --arg run_command "$ARGUS_RENDER_WORKFLOW_START_COMMAND" \
      '{
        buildConfig: ($workflow.buildConfig + {buildCommand: $build_command}),
        runCommand: $run_command,
        autoDeployTrigger: "off"
      }'
  )"

  curl -fsS \
    --request PATCH \
    --url "https://api.render.com/v1/workflows/${WORKFLOW_SERVICE_ID}" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json" \
    --header "Content-Type: application/json" \
    --data "$update_payload" \
    >/dev/null

  echo "synced ${WORKFLOW_SERVICE_ID}:workflow-runtime"
  put_render_env "$WORKFLOW_SERVICE_ID" POETRY_VERSION "$ARGUS_RENDER_POETRY_VERSION"
}

sync_workflow_release() {
  require_local_env RENDER_API_KEY
  local commit="${1:-}"
  if [ -z "$commit" ]; then
    commit="$(git rev-parse HEAD)"
  fi

  render workflows versions release "$WORKFLOW_SERVICE_ID" \
    --commit "$commit" \
    --wait \
    --confirm
}

command="${1:-}"
case "$command" in
  api-status)
    print_api_status
    ;;
  api-safe-off)
    sync_api_safe_off
    ;;
  api-proof-shadow-on)
    sync_api_proof_shadow_on
    ;;
  api-real-workflow-on)
    sync_api_real_workflow_on
    ;;
  api-runtime)
    sync_api_runtime
    ;;
  api-dispatch-on)
    echo "api-dispatch-on is an alias for api-proof-shadow-on"
    sync_api_proof_shadow_on
    ;;
  api-dispatch-off)
    echo "api-dispatch-off is an alias for api-safe-off"
    sync_api_safe_off
    ;;
  workflow-proof)
    sync_workflow_proof
    ;;
  workflow-release)
    sync_workflow_release "${2:-}"
    ;;
  workflow-runtime)
    sync_workflow_runtime
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac

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
  .github/render-env-sync.sh api-dispatch-on
  .github/render-env-sync.sh api-dispatch-off
  .github/render-env-sync.sh workflow-proof
  .github/render-env-sync.sh workflow-runtime

Commands:
  api-status        Print redacted API dispatch env status for argus-api.
  api-dispatch-on   Enable shadow job creation + Render Workflow dispatch on argus-api.
  api-dispatch-off  Disable API shadow job creation + dispatch and blank its Render key.
  workflow-proof    Sync workflow proof DB/task env vars on argus-backtests.
  workflow-runtime  Sync workflow build/start commands on argus-backtests.

Required local env:
  RENDER_API_KEY

Additional local env for workflow-proof:
  ARGUS_WORKFLOW_DATABASE_URL or SUPABASE_POSTGRES_TRANSACTION_POOLER_URL
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

  curl -fsS \
    --request DELETE \
    --url "https://api.render.com/v1/services/${service_id}/env-vars/${key}" \
    --header "Authorization: Bearer ${RENDER_API_KEY}" \
    --header "Accept: application/json" \
    >/dev/null

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

sync_api_dispatch_on() {
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

sync_api_dispatch_off() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED false
  delete_render_env "$API_SERVICE_ID" RENDER_API_KEY
}

sync_workflow_proof() {
  require_local_env RENDER_API_KEY
  local workflow_database_url="${ARGUS_WORKFLOW_DATABASE_URL:-${SUPABASE_POSTGRES_TRANSACTION_POOLER_URL:-}}"
  if [ -z "$workflow_database_url" ] || [[ "$workflow_database_url" == YOUR_* ]] || [[ "$workflow_database_url" == your_* ]]; then
    echo "ARGUS_WORKFLOW_DATABASE_URL or SUPABASE_POSTGRES_TRANSACTION_POOLER_URL is required."
    exit 1
  fi

  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_WORKFLOW_DATABASE_URL "$workflow_database_url"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_RENDER_WORKFLOW_PROOF_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_WORKFLOW_PROOF_PLAN "${ARGUS_WORKFLOW_PROOF_PLAN:-starter}"
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
}

command="${1:-}"
case "$command" in
  api-status)
    print_api_status
    ;;
  api-dispatch-on)
    sync_api_dispatch_on
    ;;
  api-dispatch-off)
    sync_api_dispatch_off
    ;;
  workflow-proof)
    sync_workflow_proof
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

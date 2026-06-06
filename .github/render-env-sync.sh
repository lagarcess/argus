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
  .github/render-env-sync.sh api-dispatch-on
  .github/render-env-sync.sh api-dispatch-off
  .github/render-env-sync.sh workflow-proof

Commands:
  api-dispatch-on   Enable shadow job creation + Render Workflow dispatch on argus-api.
  api-dispatch-off  Disable API shadow job creation + dispatch on argus-api.
  workflow-proof    Sync workflow proof DB/task env vars on argus-backtests.

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

sync_api_dispatch_on() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  put_render_env "$API_SERVICE_ID" RENDER_API_KEY "$RENDER_API_KEY"
}

sync_api_dispatch_off() {
  require_local_env RENDER_API_KEY
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_SHADOW_ENABLED false
  put_render_env "$API_SERVICE_ID" ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED false
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

command="${1:-}"
case "$command" in
  api-dispatch-on)
    sync_api_dispatch_on
    ;;
  api-dispatch-off)
    sync_api_dispatch_off
    ;;
  workflow-proof)
    sync_workflow_proof
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac

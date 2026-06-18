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
WEB_SERVICE_ID="${ARGUS_RENDER_WEB_SERVICE_ID:-$ARGUS_PRIVATE_LAUNCH_WEB_SERVICE_ID}"
WORKFLOW_SERVICE_ID="${ARGUS_RENDER_WORKFLOW_SERVICE_ID:-$ARGUS_RENDER_BACKTESTS_WORKFLOW_ID}"

usage() {
  cat <<'USAGE'
Usage:
  .github/render-env-sync.sh api-status
  .github/render-env-sync.sh api-deploy-status
  .github/render-env-sync.sh web-deploy-status
  .github/render-env-sync.sh api-safe-off
  .github/render-env-sync.sh api-proof-shadow-on
  .github/render-env-sync.sh api-real-workflow-on
  .github/render-env-sync.sh api-runtime
  .github/render-env-sync.sh release-config-audit --expect-mode <safe-off|proof-shadow|real-workflow>
  .github/render-env-sync.sh workflow-proof
  .github/render-env-sync.sh workflow-release [commit]
  .github/render-env-sync.sh workflow-runtime

Commands:
  api-status              Print redacted API workflow env status for argus-api.
  api-deploy-status       Print latest argus-api deploy status and commit.
  web-deploy-status       Print latest argus-app deploy status and commit.
  api-safe-off            Disable API job dispatch/execution and blank its Render key.
  api-proof-shadow-on     Enable proof-only shadow dispatch to workflow_proof.
  api-real-workflow-on    Enable real async dispatch to run_backtest_job.
  api-runtime             Sync argus-api build/start commands and Poetry pin.
  release-config-audit    Read-only API/web env audit with redacted fingerprint.
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

ARGUS_RELEASE_API_ENV_EXPECTED=(
  "APP_ENV=production"
  "POETRY_VERSION=$ARGUS_RENDER_POETRY_VERSION"
  "ARGUS_PERSISTENCE_MODE=supabase"
  "ARGUS_DEV_MEMORY_FALLBACK=false"
  "ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider"
  "MARKET_DATA_CACHE_TTL=43200"
  "ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS=180"
  "ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS=15"
  "ARGUS_CHECKPOINTER_MODE=postgres"
  "ARGUS_MOCK_AUTH=false"
  "ARGUS_CORS_ALLOW_ORIGINS=$ARGUS_PRIVATE_LAUNCH_CORS_ORIGINS"
  "ARGUS_STRATEGIES_ENABLED=false"
  "ARGUS_BACKTEST_WORKFLOW_TASK=$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"
  "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"
  "ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT=1"
  "ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT=2"
  "ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT=5"
  "ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT=10"
  "ARGUS_CONTEXT_PACKETS_ENABLED=true"
  "ARGUS_CONTEXT_PACKET_BUDGET_SECONDS=4"
  "ARGUS_TITLE_AUTOGEN_ENABLED=true"
  "ARGUS_TITLE_AUTOGEN_TIMEOUT_MS=250"
  "ARGUS_READINESS_ASSET_TIMEOUT_SECONDS=25"
  "ARGUS_OPS_TOKEN=<redacted-present>"
  "DATABASE_URL=<redacted-present>"
  "SUPABASE_URL=https://lgdhvepyrzbnscqssgqq.supabase.co"
  "SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxnZGh2ZXB5cnpibnNjcXNzZ3FxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2NzkwOTksImV4cCI6MjA4ODI1NTA5OX0.mc7KjmJYuAp01Mj96gceGsAW2UPI2_HQsv0_kyWaQmo"
  "SUPABASE_SERVICE_ROLE_KEY=<redacted-present>"
  "SUPABASE_JWT_SECRET=<redacted-present>"
  "OPENROUTER_API_KEY=<redacted-present>"
  "ARGUS_UTILITY_MODEL=qwen/qwen3.5-9b"
  "ARGUS_UTILITY_FALLBACK_MODEL=google/gemini-2.5-flash-lite"
  "ARGUS_CHAT_MODEL=deepseek/deepseek-v4-flash"
  "ARGUS_CHAT_FALLBACK_MODEL=qwen/qwen3.5-9b"
  "ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS=30"
  "ARGUS_STRUCTURED_MODEL=mistralai/mistral-small-2603"
  "ARGUS_STRUCTURED_FALLBACK_MODEL=deepseek/deepseek-v4-flash"
  "ARGUS_CONTEXT_MODEL=openai/gpt-oss-120b"
  "ARGUS_CONTEXT_FALLBACK_MODEL=deepseek/deepseek-v4-flash"
  "ALPACA_API_KEY=<redacted-present>"
  "ALPACA_SECRET_KEY=<redacted-present>"
  "ALPACA_PAPER_TRADING=true"
)

ARGUS_RELEASE_WEB_ENV_EXPECTED=(
  "NEXT_PUBLIC_APP_ENV=production"
  "NEXT_PUBLIC_SUPABASE_URL=https://lgdhvepyrzbnscqssgqq.supabase.co"
  "NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxnZGh2ZXB5cnpibnNjcXNzZ3FxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2NzkwOTksImV4cCI6MjA4ODI1NTA5OX0.mc7KjmJYuAp01Mj96gceGsAW2UPI2_HQsv0_kyWaQmo"
  "NEXT_PUBLIC_POSTHOG_KEY=<missing-or-empty>"
  "NEXT_PUBLIC_MOCK_AUTH=false"
  "NEXT_PUBLIC_ENABLE_SPANISH=true"
  "NEXT_PUBLIC_ARGUS_API_URL=$ARGUS_PRIVATE_LAUNCH_API_BASE_URL"
  "NEXT_PUBLIC_STRATEGIES_ENABLED=false"
  "NEXT_PUBLIC_COLLECTIONS_ENABLED=false"
  "NEXT_PUBLIC_OMNISEARCH_ENABLED=false"
  "NEXT_PUBLIC_PRIVATE_ALPHA_ONBOARDING_ENABLED=false"
  "NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false"
)

AUDIT_FAILURES=0
AUDIT_FINGERPRINT_ROWS=()

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
    --url "https://api.render.com/v1/services/${service_id}/env-vars?limit=100" \
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

render_service_deploy_json() {
  local service_id="$1"

  curl -fsS \
    --request GET \
    --url "https://api.render.com/v1/services/${service_id}/deploys?limit=1" \
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

print_deploy_status() {
  local service_id="$1"
  local service_name="$2"

  render_service_deploy_json "$service_id" | jq -r --arg service_name "$service_name" '
    .[0].deploy as $deploy
    | if $deploy == null then
        "service=\($service_name)",
        "deploy_id=<missing>",
        "status=<missing>",
        "commit=<missing>",
        "commit_short=<missing>"
      else
        ($deploy.commit.id // "") as $commit
        | "service=\($service_name)",
          "deploy_id=\($deploy.id // "<missing>")",
          "status=\($deploy.status // "<missing>")",
          "commit=\(if $commit == "" then "<missing>" else $commit end)",
          "commit_short=\(if $commit == "" then "<missing>" else $commit[0:7] end)",
          "created_at=\($deploy.createdAt // "<missing>")",
          "finished_at=\($deploy.finishedAt // "<missing>")"
      end
  '
}

print_api_deploy_status() {
  require_local_env RENDER_API_KEY
  print_deploy_status "$API_SERVICE_ID" "argus-api"
}

print_web_deploy_status() {
  require_local_env RENDER_API_KEY
  print_deploy_status "$WEB_SERVICE_ID" "argus-app"
}

is_secret_render_env_key() {
  local key="$1"
  case "$key" in
    ARGUS_OPS_TOKEN|DATABASE_URL|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_JWT_SECRET|RENDER_API_KEY|OPENROUTER_API_KEY|ALPACA_API_KEY|ALPACA_SECRET_KEY|NEXT_PUBLIC_POSTHOG_KEY)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

render_env_raw_value() {
  local env_json="$1"
  local key="$2"

  jq -r --arg key "$key" '
    [ .[]?.envVar? ] as $vars
    | ($vars | map(select(.key == $key)) | .[0].value // "")
  ' <<< "$env_json"
}

render_env_keys() {
  local env_json="$1"

  jq -r '
    [ .[]?.envVar? ] as $vars
    | $vars[]
    | .key // empty
  ' <<< "$env_json"
}

render_env_has_key() {
  local env_json="$1"
  local key="$2"

  jq -e --arg key "$key" '
    [ .[]?.envVar? ] as $vars
    | any($vars[]; .key == $key)
  ' <<< "$env_json" >/dev/null
}

list_contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    if [ "$item" = "$needle" ]; then
      return 0
    fi
  done
  return 1
}

render_env_status_value() {
  local env_json="$1"
  local key="$2"
  local value

  value="$(render_env_raw_value "$env_json" "$key")"
  if is_secret_render_env_key "$key"; then
    if [ -z "$value" ]; then
      echo "<missing-or-empty>"
    else
      echo "<redacted-present>"
    fi
    return
  fi
  if [ -z "$value" ]; then
    echo "<missing>"
    return
  fi
  echo "$value"
}

audit_expected_value() {
  local env_json="$1"
  local service="$2"
  local key="$3"
  local expected="$4"
  local actual

  actual="$(render_env_status_value "$env_json" "$key")"
  AUDIT_FINGERPRINT_ROWS+=("${service}:${key}=${actual}")
  if [ "$actual" = "$expected" ]; then
    echo "ok ${service}:${key}=${actual}"
    return
  fi

  echo "drift ${service}:${key} expected=${expected} actual=${actual}"
  AUDIT_FAILURES=$((AUDIT_FAILURES + 1))
}

audit_render_service_config() {
  local env_json="$1"
  local service="$2"
  shift 2

  local pair key expected
  for pair in "$@"; do
    key="${pair%%=*}"
    expected="${pair#*=}"
    audit_expected_value "$env_json" "$service" "$key" "$expected"
  done
}

audit_forbidden_render_env_keys() {
  local env_json="$1"
  local service="$2"
  shift 2

  local key
  for key in "$@"; do
    if render_env_has_key "$env_json" "$key"; then
      AUDIT_FINGERPRINT_ROWS+=("${service}:${key}=<forbidden>")
      echo "forbidden ${service}:${key} forbidden_legacy_env"
      AUDIT_FAILURES=$((AUDIT_FAILURES + 1))
    fi
  done
}

audit_unexpected_render_env_keys() {
  local env_json="$1"
  local service="$2"
  shift 2

  local key
  while IFS= read -r key; do
    if [ -z "$key" ]; then
      continue
    fi
    if list_contains "$key" "${ARGUS_FORBIDDEN_LEGACY_ENV[@]}"; then
      continue
    fi
    if list_contains "$key" "$@"; then
      continue
    fi
    AUDIT_FINGERPRINT_ROWS+=("${service}:${key}=<unexpected>")
    echo "forbidden ${service}:${key} unexpected_live_env"
    AUDIT_FAILURES=$((AUDIT_FAILURES + 1))
  done < <(render_env_keys "$env_json")
}

expected_api_mode_pairs() {
  local mode="$1"
  case "$mode" in
    safe-off)
      printf "%s\n" \
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=false" \
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=false" \
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false" \
        "RENDER_API_KEY=<missing-or-empty>"
      ;;
    proof-shadow)
      printf "%s\n" \
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true" \
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=true" \
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false" \
        "RENDER_API_KEY=<redacted-present>"
      ;;
    real-workflow)
      printf "%s\n" \
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true" \
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=true" \
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true" \
        "RENDER_API_KEY=<redacted-present>"
      ;;
    *)
      echo "Unknown expected API mode: $mode"
      return 2
      ;;
  esac
}

render_env_fingerprint() {
  if command -v sha256sum >/dev/null 2>&1; then
    printf "%s\n" "${AUDIT_FINGERPRINT_ROWS[@]}" | LC_ALL=C sort | sha256sum | awk '{print $1}'
    return
  fi
  printf "%s\n" "${AUDIT_FINGERPRINT_ROWS[@]}" | LC_ALL=C sort | shasum -a 256 | awk '{print $1}'
}

audit_release_config() {
  local expected_mode=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --expect-mode)
        expected_mode="${2:-}"
        if [ -z "$expected_mode" ]; then
          echo "--expect-mode requires a value."
          return 2
        fi
        shift 2
        ;;
      *)
        echo "Unknown release-config-audit argument: $1"
        return 2
        ;;
    esac
  done
  if [ -z "$expected_mode" ]; then
    echo "release-config-audit requires --expect-mode <safe-off|proof-shadow|real-workflow>."
    return 2
  fi
  case "$expected_mode" in
    safe-off|proof-shadow|real-workflow)
      ;;
    *)
      echo "Unknown expected API mode: $expected_mode"
      return 2
      ;;
  esac

  require_local_env RENDER_API_KEY
  AUDIT_FAILURES=0
  AUDIT_FINGERPRINT_ROWS=()

  local api_env_json web_env_json workflow_task real_workflow_task fingerprint
  local mode_pairs=()
  local mode_pair
  while IFS= read -r mode_pair; do
    mode_pairs+=("$mode_pair")
  done < <(expected_api_mode_pairs "$expected_mode")
  api_env_json="$(render_env_json "$API_SERVICE_ID")"
  web_env_json="$(render_env_json "$WEB_SERVICE_ID")"

  echo "Argus release config audit"
  echo "expected_mode=$expected_mode"
  audit_forbidden_render_env_keys "$api_env_json" "argus-api" "${ARGUS_FORBIDDEN_LEGACY_ENV[@]}"
  audit_forbidden_render_env_keys "$web_env_json" "argus-app" "${ARGUS_FORBIDDEN_LEGACY_ENV[@]}"
  audit_unexpected_render_env_keys "$api_env_json" "argus-api" "${ARGUS_RENDER_API_ENV[@]}"
  audit_unexpected_render_env_keys "$web_env_json" "argus-app" "${ARGUS_RENDER_WEB_ENV[@]}"
  audit_render_service_config "$api_env_json" "argus-api" "${ARGUS_RELEASE_API_ENV_EXPECTED[@]}"
  audit_render_service_config "$api_env_json" "argus-api" "${mode_pairs[@]}"
  audit_render_service_config "$web_env_json" "argus-app" "${ARGUS_RELEASE_WEB_ENV_EXPECTED[@]}"

  workflow_task="$(render_env_status_value "$api_env_json" ARGUS_BACKTEST_WORKFLOW_TASK)"
  real_workflow_task="$(render_env_status_value "$api_env_json" ARGUS_BACKTEST_REAL_WORKFLOW_TASK)"
  fingerprint="$(render_env_fingerprint)"

  echo "workflow_task=$workflow_task"
  echo "real_workflow_task=$real_workflow_task"
  echo "env_fingerprint=$fingerprint"
  if [ "$AUDIT_FAILURES" -eq 0 ]; then
    echo "status=ready"
    return 0
  fi
  echo "status=drift"
  return 1
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
  put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS "${ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS:-30}"
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
  api-deploy-status)
    print_api_deploy_status
    ;;
  web-deploy-status)
    print_web_deploy_status
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
  release-config-audit)
    shift
    audit_release_config "$@"
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

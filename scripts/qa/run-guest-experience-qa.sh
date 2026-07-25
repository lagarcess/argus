#!/bin/bash
# Exact-head, local-only Block 4 guest browser QA.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mode="${1:-}"
case "$mode" in
  list|preflight|authoritative) ;;
  *)
    echo "usage: scripts/qa/run-guest-experience-qa.sh list|preflight|authoritative" >&2
    exit 2
    ;;
esac
shift

expected_root="/Users/garces/.codex/worktrees/2f927a60-b587-4135-aff4-24020c81fe93/private-alpha-next"
actual_root="$(git rev-parse --show-toplevel)"
[ "$actual_root" = "$expected_root" ] || {
  echo "guest QA refused: wrong worktree" >&2
  exit 1
}
[ "$(git branch --show-current)" = "codex/guest-experience" ] || {
  echo "guest QA refused: wrong or detached branch" >&2
  exit 1
}

status="$(git status --porcelain)"
if [ -n "$status" ]; then
  if [ "$mode" = "authoritative" ]; then
    echo "guest QA refused: authoritative run requires a clean worktree" >&2
    exit 1
  fi
  invalid_path="$(
    git status --porcelain |
      sed -E 's/^.. //' |
      grep -Ev '^(web/e2e/|web/__tests__/guest-browser-harness\.test\.ts$|scripts/qa/README\.md$|scripts/qa/run-guest-experience-qa\.sh$)' |
      head -1 || true
  )"
  [ -z "$invalid_path" ] || {
    echo "guest QA refused: preflight contains a non-harness change" >&2
    exit 1
  }
  export ARGUS_GUEST_QA_ALLOW_TEST_DIFF=true
else
  unset ARGUS_GUEST_QA_ALLOW_TEST_DIFF || true
fi

export ARGUS_CANDIDATE_SHA="$(git rev-parse HEAD)"
unset ARGUS_QA_APPROVED_SUPABASE_REF || true

# Load live provider/model credentials, then replace every database/Auth target
# with the disposable local Supabase stack before a service or browser starts.
# shellcheck disable=SC1091
source .github/argus-env.sh
argus_load_root_env
eval "$(supabase status -o env)"

for required in API_URL ANON_KEY SERVICE_ROLE_KEY DB_URL JWT_SECRET; do
  value="${!required:-}"
  [ -n "$value" ] || {
    echo "guest QA refused: local Supabase did not provide $required" >&2
    exit 1
  }
done

case "$API_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *)
    echo "guest QA refused: Supabase API is not loopback-local" >&2
    exit 1
    ;;
esac
case "$DB_URL" in
  postgresql://*@127.0.0.1:*/*|postgresql://*@localhost:*/*) ;;
  *)
    echo "guest QA refused: Supabase database is not loopback-local" >&2
    exit 1
    ;;
esac

export SUPABASE_PROJECT_URL="$API_URL"
export SUPABASE_URL="$API_URL"
export NEXT_PUBLIC_SUPABASE_URL="$API_URL"
export SUPABASE_ANON_PUBLIC_KEY="$ANON_KEY"
export SUPABASE_ANON_KEY="$ANON_KEY"
export NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY"
export SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY"
export SUPABASE_JWT_SECRET="$JWT_SECRET"
export SUPABASE_POSTGRES_SESSION_POOLER_URL="$DB_URL"
export SUPABASE_POSTGRES_DIRECT_URL="$DB_URL"
export SUPABASE_POSTGRES_TRANSACTION_POOLER_URL="$DB_URL"
export DATABASE_URL="$DB_URL"

export ARGUS_PERSISTENCE_MODE=supabase
export ARGUS_DEV_MEMORY_FALLBACK=false
export ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider
export ARGUS_CHECKPOINTER_MODE=postgres
export ARGUS_MOCK_AUTH=false
export ARGUS_GUEST_ACCESS_ENABLED=true
export ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false
export ARGUS_PRIVATE_ALPHA_ONBOARDING_ENABLED=false
export ARGUS_CORS_ALLOW_ORIGINS=http://localhost:3000
export ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=false
export ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=false
export ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false

export ARGUS_APP_ORIGIN=http://localhost:3000
export PLAYWRIGHT_BASE_URL=http://localhost:3000
export NEXT_PUBLIC_ARGUS_API_URL=http://localhost:8000/api/v1
export NEXT_PUBLIC_MOCK_AUTH=false
export NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true
export NEXT_PUBLIC_ENABLE_SPANISH=true
export NEXT_PUBLIC_PRIVATE_ALPHA_ONBOARDING_ENABLED=false
export NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false
export NEXT_PUBLIC_STRATEGIES_ENABLED=false
export NEXT_PUBLIC_COLLECTIONS_ENABLED=false
export NEXT_PUBLIC_OMNISEARCH_ENABLED=true
export NEXT_PUBLIC_POSTHOG_KEY=
unset NEXT_PUBLIC_POSTHOG_HOST || true
unset POSTHOG_PROJECT_TOKEN POSTHOG_REGION POSTHOG_HOST \
  ARGUS_POSTHOG_TIMEOUT_SECONDS || true

if [ "$mode" = "authoritative" ]; then
  argus_require_qa_env
  export ARGUS_GUEST_QA_REQUIRE_ZERO_STATE=true
  unset ARGUS_GUEST_QA_PREFLIGHT || true
  (cd web && bun run build)
elif [ "$mode" = "preflight" ]; then
  export ARGUS_GUEST_QA_PREFLIGHT=true
  export ARGUS_GUEST_QA_REQUIRE_ZERO_STATE=false
else
  unset ARGUS_GUEST_QA_PREFLIGHT || true
  export ARGUS_GUEST_QA_REQUIRE_ZERO_STATE=false
fi

cd web
exec bunx playwright test \
  --config=e2e/guest-experience.playwright.config.ts \
  --project=chromium \
  --workers=1 \
  "$@"

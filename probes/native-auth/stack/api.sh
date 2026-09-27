#!/usr/bin/env bash
# Run the unchanged Argus API against the lane stack. Provider keys are blanked
# so no model, market-data, or email provider can be reached.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
eval "$(native_auth_supabase status -o env)"
case "$API_URL" in http://127.0.0.1:*|http://localhost:*) ;; *) echo "non-loopback stack" >&2; exit 1;; esac
cd "$NATIVE_AUTH_ROOT"
exec env \
  SUPABASE_PROJECT_URL="$API_URL" SUPABASE_URL="$API_URL" \
  SUPABASE_ANON_PUBLIC_KEY="$ANON_KEY" SUPABASE_ANON_KEY="$ANON_KEY" \
  SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" SUPABASE_JWT_SECRET="$JWT_SECRET" \
  SUPABASE_POSTGRES_SESSION_POOLER_URL="$DB_URL" DATABASE_URL="$DB_URL" \
  ARGUS_PERSISTENCE_MODE=supabase \
  ALPACA_API_KEY= ALPACA_SECRET_KEY= OPENROUTER_API_KEY= OPENAI_API_KEY= \
  ANTHROPIC_API_KEY= RESEND_API_KEY= PERPLEXITY_API_KEY= EXA_API_KEY= \
  POSTHOG_API_KEY= SENTRY_DSN= \
  ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
  ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
  ARGUS_GUEST_ACCESS_ENABLED=true ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false \
  NEXT_PUBLIC_MOCK_AUTH=false ARGUS_MOCK_AUTH=false \
  poetry run uvicorn argus.api.main:app --host 127.0.0.1 --port "$NATIVE_AUTH_API_PORT"

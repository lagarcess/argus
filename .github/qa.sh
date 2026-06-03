#!/bin/bash
# QA Mode: production-parity browser QA.
# Usage: .github/qa.sh
#
# This script is authoritative for backend QA runtime flags. It intentionally
# uses real Supabase persistence, strict failures, Postgres checkpoints, and the
# live provider catalog so manual QA catches provider-resolution issues.

set -eo pipefail

if [ ! -f .env ]; then
  echo "❌ Root .env missing. Copy .env.example to .env and fill QA credentials."
  exit 1
fi

set -a
set +u
# shellcheck disable=SC1091
source .env
set -u
set +a

require_env() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "$value" ] || [[ "$value" == YOUR_* ]] || [[ "$value" == your_* ]]; then
    echo "❌ $name is required for QA mode."
    exit 1
  fi
}

require_env "SUPABASE_PROJECT_URL"
require_env "SUPABASE_ANON_PUBLIC_KEY"
require_env "SUPABASE_SERVICE_ROLE_KEY"
require_env "SUPABASE_JWT_SECRET"
require_env "SUPABASE_POSTGRES_SESSION_POOLER_URL"
require_env "ALPACA_API_KEY"
require_env "ALPACA_SECRET_KEY"
require_env "OPENROUTER_API_KEY"

export ARGUS_PERSISTENCE_MODE=supabase
export ARGUS_DEV_MEMORY_FALLBACK=false
export ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider
export ARGUS_CHECKPOINTER_MODE=postgres
export ARGUS_MOCK_AUTH=false
# SUPABASE_POSTGRES_DIRECT_URL and SUPABASE_POSTGRES_TRANSACTION_POOLER_URL may
# be present in .env for migrations or future serverless-style clients. QA uses
# session pooling for the persistent local backend/checkpointer runtime.
export DATABASE_URL="$SUPABASE_POSTGRES_SESSION_POOLER_URL"

echo "🟢 QA Mode activated:"
echo "   - Persistence: Supabase (durable)"
echo "   - Market Data: Live provider catalog (production-like asset resolution)"
echo "   - Fallback: Strict (errors exposed for debugging)"
echo "   - Runtime checkpoints: Postgres"
echo "   - Database URL: Session Pooler -> internal DATABASE_URL"
echo ""
echo "Frontend QA reminder:"
echo "   web/.env.local should use NEXT_PUBLIC_MOCK_AUTH=false for real auth"
echo "   and NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1"
echo ""
echo "Starting FastAPI backend on http://127.0.0.1:8000"
echo ""

poetry run fastapi dev src/argus/api/main.py

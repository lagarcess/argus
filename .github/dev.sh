#!/bin/bash
# Dev Mode: fast iteration with memory persistence and synthetic data.
# Usage: .github/dev.sh
#
# This script is authoritative for backend dev-mode runtime flags. The root
# .env file provides secrets/defaults when present, but mode flags below win.

set -eo pipefail

if [ -f .env ]; then
  set -a
  set +u
  # shellcheck disable=SC1091
  source .env
  set -u
  set +a
else
  echo "⚠️  Root .env missing. Dev mode can still start with synthetic assets,"
  echo "   but copy .env.example to .env when you need provider/LLM credentials."
  set -u
fi

export ARGUS_PERSISTENCE_MODE=memory
export ARGUS_DEV_MEMORY_FALLBACK=true
export ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture
export ARGUS_CHECKPOINTER_MODE=memory
export ARGUS_MOCK_AUTH=true
# Dev mode is intentionally memory-only even if .env contains typed Supabase
# Postgres URLs such as SUPABASE_POSTGRES_SESSION_POOLER_URL.
unset DATABASE_URL

echo "🔵 Dev Mode activated:"
echo "   - Persistence: Memory (ephemeral)"
echo "   - Market Data: Synthetic fixtures (no API calls)"
echo "   - Fallback: Tolerant (keeps going on errors)"
echo "   - Runtime checkpoints: Memory"
echo "   - Database URLs: Ignored"
echo ""
echo "Starting FastAPI backend on http://127.0.0.1:8000"
echo ""

poetry run fastapi dev src/argus/api/main.py

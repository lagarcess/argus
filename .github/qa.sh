#!/bin/bash
# QA Mode: Production parity with Supabase persistence and recorded fixtures
# Usage: .github/qa.sh

set -a
source .env
set +a

export ARGUS_PERSISTENCE_MODE=supabase
export ARGUS_DEV_MEMORY_FALLBACK=false
export ARGUS_MARKET_DATA_PROVIDER_MODE=recorded_provider_fixture
export ARGUS_CHECKPOINTER_MODE=postgres

echo "🟢 QA Mode activated:"
echo "   - Persistence: Supabase (durable)"
echo "   - Market Data: Recorded fixtures (production-like)"
echo "   - Fallback: Strict (errors exposed for debugging)"
echo ""
echo "Starting FastAPI backend on http://127.0.0.1:8000"
echo ""

poetry run fastapi dev src/argus/api/main.py

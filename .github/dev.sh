#!/bin/bash
# Dev Mode: Fast iteration with memory persistence and synthetic data
# Usage: .github/dev.sh

set -a
source .env
set +a

export ARGUS_PERSISTENCE_MODE=memory
export ARGUS_DEV_MEMORY_FALLBACK=true
export ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture
export ARGUS_CHECKPOINTER_MODE=memory

echo "🔵 Dev Mode activated:"
echo "   - Persistence: Memory (ephemeral)"
echo "   - Market Data: Synthetic fixtures (no API calls)"
echo "   - Fallback: Tolerant (keeps going on errors)"
echo ""
echo "Starting FastAPI backend on http://127.0.0.1:8000"
echo ""

poetry run fastapi dev src/argus/api/main.py

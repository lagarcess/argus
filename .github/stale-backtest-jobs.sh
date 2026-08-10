#!/bin/bash
# Explicit-target stale queued/running backtest reconciliation for readiness.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -n "${ARGUS_STALE_JOBS_SUPABASE_URL:-}" ]; then
  export SUPABASE_URL="$ARGUS_STALE_JOBS_SUPABASE_URL"
fi
if [ -n "${ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  export SUPABASE_SERVICE_ROLE_KEY="$ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY"
fi

poetry run python scripts/ops/stale_backtest_jobs.py "$@"

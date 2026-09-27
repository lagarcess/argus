#!/usr/bin/env bash
# Usage: run.sh <suite> <evidence-json> [probe args]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../stack/env.sh"
eval "$(native_auth_supabase status -o env 2>/dev/null)"
export API_URL ANON_KEY SERVICE_ROLE_KEY DB_URL MAILPIT_URL
export NATIVE_AUTH_ARGUS_API="${NATIVE_AUTH_ARGUS_API:-http://127.0.0.1:$NATIVE_AUTH_API_PORT}"
exec "$NATIVE_AUTH_ROOT/.venv/bin/python" "$HERE/probe.py" "$@"

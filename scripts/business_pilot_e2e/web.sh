#!/bin/bash
# web.sh [off]: next dev on 3621 against the local API; "off" leaves the Business flag unset.
set -a; source "$(dirname "$0")/stack.env"; set +a
cd /Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-spaces/web
[ "${1:-}" = off ] || export NEXT_PUBLIC_BUSINESS_PILOT_ENABLED=true
export NEXT_PUBLIC_SUPABASE_URL="$API_URL"
export NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY"
export NEXT_PUBLIC_ARGUS_API_URL=http://localhost:8621/api/v1
export NEXT_PUBLIC_MOCK_AUTH=false
export NEXT_PUBLIC_ENABLE_SPANISH=true
export NEXT_TELEMETRY_DISABLED=1
unset API_URL ANON_KEY SERVICE_ROLE_KEY SECRET_KEY JWT_SECRET DB_URL PUBLISHABLE_KEY
exec node ./node_modules/next/dist/bin/next dev --port 3621

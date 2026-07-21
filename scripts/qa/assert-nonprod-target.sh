#!/bin/bash
# Fail-closed target guard for issue-248 auth QA.
# Destructive auth QA may only target loopback local Supabase or the single
# approved QA branch ref supplied via ARGUS_QA_APPROVED_SUPABASE_REF.
# Any reference to the production project ref anywhere in the QA env aborts.
set -euo pipefail

PRODUCTION_SUPABASE_REF="lgdhvepyrzbnscqssgqq"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
WEB_ENV_FILE="$ROOT_DIR/web/.env.local"
APPROVED_REF="${ARGUS_QA_APPROVED_SUPABASE_REF:-}"

fail() {
  echo "❌ nonprod-guard: $1" >&2
  exit 1
}

[ -f "$ENV_FILE" ] || fail ".env missing; run scripts/qa/write-local-env.sh first"
[ -f "$WEB_ENV_FILE" ] || fail "web/.env.local missing; run scripts/qa/write-local-env.sh first"

for f in "$ENV_FILE" "$WEB_ENV_FILE"; do
  if grep -q "$PRODUCTION_SUPABASE_REF" "$f"; then
    fail "$(basename "$f") references the production Supabase project"
  fi
done

if [ -n "$APPROVED_REF" ] && [ "$APPROVED_REF" = "$PRODUCTION_SUPABASE_REF" ]; then
  fail "ARGUS_QA_APPROVED_SUPABASE_REF must never be the production project"
fi

check_var() {
  local file="$1" name="$2" value
  value="$(grep -E "^${name}=" "$file" | head -1 | cut -d= -f2- || true)"
  [ -n "$value" ] || return 0
  case "$value" in
    *"$PRODUCTION_SUPABASE_REF"*)
      fail "$name targets the production Supabase project"
      ;;
    *127.0.0.1*|*localhost*)
      return 0
      ;;
    *supabase.co*|*supabase.com*)
      if [ -n "$APPROVED_REF" ] && [[ "$value" == *"$APPROVED_REF"* ]]; then
        return 0
      fi
      fail "$name targets a hosted Supabase project that is not the approved QA branch"
      ;;
    *)
      fail "$name has an unrecognized target"
      ;;
  esac
}

for name in SUPABASE_PROJECT_URL SUPABASE_URL NEXT_PUBLIC_SUPABASE_URL \
  SUPABASE_POSTGRES_SESSION_POOLER_URL SUPABASE_POSTGRES_DIRECT_URL \
  SUPABASE_POSTGRES_TRANSACTION_POOLER_URL DATABASE_URL; do
  check_var "$ENV_FILE" "$name"
done
for name in NEXT_PUBLIC_SUPABASE_URL ARGUS_APP_ORIGIN; do
  check_var "$WEB_ENV_FILE" "$name"
done

mock_auth="$(grep -E '^NEXT_PUBLIC_MOCK_AUTH=' "$WEB_ENV_FILE" | head -1 | cut -d= -f2- || true)"
[ "$mock_auth" = "false" ] || fail "NEXT_PUBLIC_MOCK_AUTH must be false for real-auth QA"

echo "✅ nonprod-guard: every auth target is loopback-local or the approved QA branch"

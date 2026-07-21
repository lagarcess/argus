#!/bin/bash
# Creates disposable issue-248 QA identities through the real Argus signup path
# so auth users and profiles exist exactly as production signup would create
# them. Local/approved-QA targets only; the nonprod guard gates every run.
# Portable: auth admin + PostgREST over the stack's HTTP surface, no Docker.
# Usage: setup-local-identities.sh [--teardown]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
bash scripts/qa/assert-nonprod-target.sh

API_BASE="${ARGUS_QA_API_BASE:-http://localhost:8000/api/v1}"
eval "$(supabase status -o env)"
AUTH_ADMIN="$API_URL/auth/v1/admin"
REST_URL="$API_URL/rest/v1"

RECOVERY_EMAIL="qa-recovery-248@qa.argus.local"
SECOND_EMAIL="qa-second-248@qa.argus.local"
IDENTITY_FILE="$ROOT_DIR/.qa-identities.env"

service_curl() {
  curl -sS -H "apikey: $SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SERVICE_ROLE_KEY" "$@"
}

urlencode() {
  python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

delete_user() {
  local email="$1" ids id
  ids="$(service_curl "$AUTH_ADMIN/users?page=1&per_page=200" | python3 -c "
import json, sys
target = sys.argv[1].lower()
data = json.load(sys.stdin)
users = data.get('users', data if isinstance(data, list) else [])
print('\n'.join(u['id'] for u in users if (u.get('email') or '').lower() == target))
" "$email")"
  for id in $ids; do
    service_curl -X DELETE "$AUTH_ADMIN/users/$id" > /dev/null
  done
  service_curl -X DELETE \
    "$REST_URL/profiles?email=eq.$(urlencode "$email")" \
    -H "Prefer: return=minimal" > /dev/null
}

if [ "${1:-}" = "--teardown" ]; then
  delete_user "$RECOVERY_EMAIL"
  delete_user "$SECOND_EMAIL"
  rm -f "$IDENTITY_FILE"
  echo "✅ QA identities removed"
  exit 0
fi

signup() {
  local email="$1" password="$2" language="$3" display="$4" code
  code="$(curl -sS -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$API_BASE/auth/signup" \
    -d "{\"email\":\"$email\",\"password\":\"$password\",\"display_name\":\"$display\",\"language\":\"$language\"}")"
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "❌ signup for $email returned HTTP $code" >&2
    exit 1
  fi
}

verify_login() {
  local email="$1" password="$2" code
  code="$(curl -sS -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST "$API_BASE/auth/login" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}")"
  if [ "$code" != "200" ]; then
    echo "❌ login verification for $email returned HTTP $code" >&2
    exit 1
  fi
}

# Fresh identities invalidate any persisted password state from prior runs.
rm -f "$ROOT_DIR/temp/qa-evidence-248/qa-state.json"

RECOVERY_PASSWORD="Qa!$(openssl rand -hex 12)"
SECOND_PASSWORD="Qa!$(openssl rand -hex 12)"

delete_user "$RECOVERY_EMAIL"
delete_user "$SECOND_EMAIL"
signup "$RECOVERY_EMAIL" "$RECOVERY_PASSWORD" "en" "QA Recovery"
signup "$SECOND_EMAIL" "$SECOND_PASSWORD" "es-419" "QA Segunda"
verify_login "$RECOVERY_EMAIL" "$RECOVERY_PASSWORD"
verify_login "$SECOND_EMAIL" "$SECOND_PASSWORD"

umask 177
cat > "$IDENTITY_FILE" <<EOF
# Untracked runtime credentials for disposable local/QA-branch identities.
QA_RECOVERY_EMAIL=$RECOVERY_EMAIL
QA_RECOVERY_PASSWORD=$RECOVERY_PASSWORD
QA_SECOND_EMAIL=$SECOND_EMAIL
QA_SECOND_PASSWORD=$SECOND_PASSWORD
EOF

echo "✅ QA identities ready (credentials in .qa-identities.env, untracked)"

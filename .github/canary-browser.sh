#!/bin/bash
# Browser proof for the Spanish private-alpha release entry path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/argus-env.sh"
argus_load_root_env >/dev/null || true

RELEASE_PROFILE_TOOL="$SCRIPT_DIR/private-alpha-release-profile.py"
APP_URL="${ARGUS_CANARY_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"
EMAIL="${ARGUS_CANARY_EMAIL:-${MOCK_USER_EMAIL:-}}"
PASSWORD="${ARGUS_CANARY_PASSWORD:-${MOCK_USER_PASSWORD:-}}"

if ! python3 "$RELEASE_PROFILE_TOOL" validate >/dev/null; then
  echo "ERROR: checked-in release profile is invalid."
  exit 1
fi
if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
  echo "ERROR: ARGUS_CANARY_EMAIL/ARGUS_CANARY_PASSWORD or mock user credentials are required."
  exit 1
fi
if [ ! -d web/node_modules/@playwright ]; then
  echo "ERROR: Playwright dependencies are missing; run bun install in web first."
  exit 1
fi

CANARY_LANGUAGE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value language)"
CANARY_STATIC_LABELS="$(python3 "$RELEASE_PROFILE_TOOL" static-key-values "$CANARY_LANGUAGE")"

echo "Running Spanish browser release canary"
cd web
ARGUS_CANARY_BROWSER_EMAIL="$EMAIL" \
ARGUS_CANARY_BROWSER_PASSWORD="$PASSWORD" \
ARGUS_CANARY_BROWSER_LANGUAGE="$CANARY_LANGUAGE" \
ARGUS_CANARY_STATIC_LABELS_JSON="$CANARY_STATIC_LABELS" \
PLAYWRIGHT_BASE_URL="$APP_URL" \
bunx playwright test e2e/private-alpha-release-canary.spec.ts --project=chromium

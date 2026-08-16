#!/bin/bash
# Authenticated browser proof for the Spanish private-alpha Golden Path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/argus-env.sh"
argus_load_root_env >/dev/null || true

RELEASE_PROFILE_TOOL="$SCRIPT_DIR/private-alpha-release-profile.py"
APP_URL="${ARGUS_CANARY_APP_URL:-$ARGUS_PRIVATE_LAUNCH_APP_URL}"
IDENTITY_HANDOFF="${ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF:-}"
STORAGE_STATE="${ARGUS_CANARY_BROWSER_STORAGE_STATE:-}"
USER_ID="${ARGUS_CANARY_BROWSER_USER_ID:-}"
ARTIFACT_PROBE="${ARGUS_CANARY_BROWSER_ARTIFACT_PROBE:-none}"
REDACTION_PROBE_VALUE="${ARGUS_CANARY_BROWSER_REDACTION_PROBE_VALUE:-}"

if ! python3 "$RELEASE_PROFILE_TOOL" validate >/dev/null; then
  echo "ERROR: checked-in release profile is invalid."
  exit 1
fi
if [ -z "$STORAGE_STATE" ] || [ ! -f "$STORAGE_STATE" ]; then
  echo "ERROR: private authenticated browser storage state is required."
  exit 1
fi
if [ -z "$IDENTITY_HANDOFF" ] || [ ! -f "$IDENTITY_HANDOFF" ]; then
  echo "ERROR: private browser identity handoff file is required."
  exit 1
fi
if [ -z "$USER_ID" ]; then
  echo "ERROR: expected canary user identity is required."
  exit 1
fi
case "$ARTIFACT_PROBE" in
  none|redacted|unredacted) ;;
  *)
    echo "ERROR: browser artifact probe is invalid."
    exit 1
    ;;
esac
if [ "$ARTIFACT_PROBE" != "none" ] && [ -z "$REDACTION_PROBE_VALUE" ]; then
  echo "ERROR: browser artifact probe value is required."
  exit 1
fi
if [ ! -d web/node_modules/@playwright ]; then
  echo "ERROR: Playwright dependencies are missing; run bun install in web first."
  exit 1
fi

CANARY_LANGUAGE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value language)"
CANARY_STATIC_LABELS="$(python3 "$RELEASE_PROFILE_TOOL" static-key-values "$CANARY_LANGUAGE")"
CANARY_PROMPT="$(python3 "$RELEASE_PROFILE_TOOL" canary-value prompt)"
CANARY_DECISION_STATE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value decision_state)"
CANARY_DECISION_NOTE="$(python3 "$RELEASE_PROFILE_TOOL" canary-value decision_note)"
CANARY_SEARCH_QUERY="$(python3 "$RELEASE_PROFILE_TOOL" canary-value search_query)"

echo "Running stored-session Spanish release canary"
cd web
env -u ARGUS_OPS_TOKEN \
  -u ARGUS_WORKFLOW_DATABASE_URL \
  -u RENDER_API_KEY \
  -u SUPABASE_SERVICE_ROLE_KEY \
  -u ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY \
  ARGUS_CANARY_BROWSER_STORAGE_STATE="$STORAGE_STATE" \
  ARGUS_CANARY_BROWSER_USER_ID="$USER_ID" \
  ARGUS_CANARY_BROWSER_LANGUAGE="$CANARY_LANGUAGE" \
  ARGUS_CANARY_STATIC_LABELS_JSON="$CANARY_STATIC_LABELS" \
  ARGUS_CANARY_BROWSER_PROMPT="$CANARY_PROMPT" \
  ARGUS_CANARY_BROWSER_DECISION_STATE="$CANARY_DECISION_STATE" \
  ARGUS_CANARY_BROWSER_DECISION_NOTE="$CANARY_DECISION_NOTE" \
  ARGUS_CANARY_BROWSER_SEARCH_QUERY="$CANARY_SEARCH_QUERY" \
  ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF="$IDENTITY_HANDOFF" \
  ARGUS_CANARY_BROWSER_ARTIFACT_PROBE="$ARTIFACT_PROBE" \
  ARGUS_CANARY_BROWSER_REDACTION_PROBE_VALUE="$REDACTION_PROBE_VALUE" \
  PLAYWRIGHT_BASE_URL="$APP_URL" \
  bunx playwright test e2e/private-alpha-release-canary.spec.ts --project=chromium

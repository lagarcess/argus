#!/bin/bash
# Resolve the coherent production SHA while preserving branch harness proof.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

: "${RENDER_API_KEY:?RENDER_API_KEY is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"

case "${GITHUB_EVENT_NAME:-}" in
  schedule|workflow_dispatch) ;;
  *)
    echo "ERROR: unsupported canary event." >&2
    exit 1
    ;;
esac

api_status="$(RENDER_API_KEY="$RENDER_API_KEY" "$SCRIPT_DIR/render-env-sync.sh" api-deploy-status)"
web_status="$(RENDER_API_KEY="$RENDER_API_KEY" "$SCRIPT_DIR/render-env-sync.sh" web-deploy-status)"
workflow_status="$(RENDER_API_KEY="$RENDER_API_KEY" "$SCRIPT_DIR/render-env-sync.sh" workflow-version-status)"
deployed_sha="$(python3 "$SCRIPT_DIR/canary-deployed-sha.py" \
  --api-status "$api_status" \
  --web-status "$web_status" \
  --workflow-status "$workflow_status")"
git cat-file -e "${deployed_sha}^{commit}"

harness_sha="$(git rev-parse HEAD)"
allow_harness_mismatch="false"
if [ "${GITHUB_EVENT_NAME}" = "schedule" ]; then
  git checkout --detach "$deployed_sha"
  harness_sha="$(git rev-parse HEAD)"
else
  # workflow_dispatch proves branch harness changes against the exact release
  # currently served by API, web, and the workflow service.
  allow_harness_mismatch="true"
fi

{
  echo "ARGUS_CANARY_SHA=$deployed_sha"
  echo "ARGUS_CANARY_HARNESS_SHA=$harness_sha"
  echo "ARGUS_CANARY_ALLOW_HARNESS_MISMATCH=$allow_harness_mismatch"
} >> "$GITHUB_ENV"

echo "canary_deployed_sha=$deployed_sha"
echo "canary_harness_sha=$harness_sha"
echo "canary_allow_harness_mismatch=$allow_harness_mismatch"

#!/bin/bash
# Warm Render free services before a private-alpha tester session.

set -euo pipefail

APP_URL="${ARGUS_WARMUP_APP_URL:-https://argus-app-suz5.onrender.com}"
API_URL="${ARGUS_WARMUP_API_URL:-https://argus-ohr5.onrender.com}"
OPS_TOKEN="${ARGUS_OPS_TOKEN:-}"
TIMEOUT_SECONDS="${ARGUS_WARMUP_TIMEOUT_SECONDS:-180}"
SLEEP_SECONDS="${ARGUS_WARMUP_SLEEP_SECONDS:-5}"

deadline=$((SECONDS + TIMEOUT_SECONDS))

wait_for_url() {
  local label="$1"
  local url="$2"
  shift 2
  local attempt=1

  echo "Warming $label: $url"
  while true; do
    if curl -fsS --max-time 15 "$@" "$url" > /dev/null; then
      echo "OK: $label responded"
      return 0
    fi

    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "ERROR: $label did not respond within ${TIMEOUT_SECONDS}s"
      return 1
    fi

    echo "  waiting for $label... attempt $attempt"
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done
}

wait_for_readiness() {
  if [ -z "$OPS_TOKEN" ]; then
    echo "ARGUS_OPS_TOKEN is required for product readiness warmup."
    return 1
  fi

  wait_for_url \
    "product readiness" \
    "${API_URL}/internal/readiness?force=true" \
    -H "Authorization: Bearer ${OPS_TOKEN}"
}

echo "Argus private-launch warmup"
echo "Timeout: ${TIMEOUT_SECONDS}s"
echo ""

wait_for_url "API health" "${API_URL}/health"
wait_for_readiness
wait_for_url "frontend" "$APP_URL"

echo ""
echo "Argus product path is ready for testers."

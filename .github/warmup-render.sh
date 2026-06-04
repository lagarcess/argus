#!/bin/bash
# Warm Render free services before a private-alpha tester session.

set -euo pipefail

APP_URL="${ARGUS_WARMUP_APP_URL:-https://argus-app-suz5.onrender.com}"
API_URL="${ARGUS_WARMUP_API_URL:-https://argus-ohr5.onrender.com}"
TIMEOUT_SECONDS="${ARGUS_WARMUP_TIMEOUT_SECONDS:-180}"
SLEEP_SECONDS="${ARGUS_WARMUP_SLEEP_SECONDS:-5}"

deadline=$((SECONDS + TIMEOUT_SECONDS))

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempt=1

  echo "Warming $label: $url"
  while true; do
    if curl -fsS --max-time 15 "$url" > /dev/null; then
      echo "✓ $label responded"
      return 0
    fi

    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "✗ $label did not respond within ${TIMEOUT_SECONDS}s"
      return 1
    fi

    echo "  waiting for $label... attempt $attempt"
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done
}

echo "Argus private-launch warmup"
echo "Timeout: ${TIMEOUT_SECONDS}s"
echo ""

wait_for_url "API health" "${API_URL}/health"
wait_for_url "frontend" "$APP_URL"

echo ""
echo "Argus is warm and ready for testers."

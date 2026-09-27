#!/usr/bin/env bash
# SYNTHETIC adapter for proposal E3. Proxies to the unchanged Argus API.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../stack/env.sh"
export NATIVE_AUTH_ADAPTER_UPSTREAM="http://127.0.0.1:$NATIVE_AUTH_API_PORT"
cd "$HERE"
exec "$NATIVE_AUTH_ROOT/.venv/bin/uvicorn" handoff_header_adapter:app \
  --host 127.0.0.1 --port "$NATIVE_AUTH_ADAPTER_PORT" --no-access-log

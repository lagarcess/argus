#!/bin/bash
set -euo pipefail

echo "Checking OpenAPI client parity..."
cd web

if ! ./node_modules/.bin/openapi-ts > /dev/null 2>&1; then
    echo "ERROR: OpenAPI client generation failed."
    exit 1
fi

if [ -n "$(git status --porcelain lib/api)" ]; then
    echo "ERROR: OpenAPI client is stale. The 'web/lib/api' directory has changes."
    echo "Please regenerate the client and commit the changes."
    # We exit 1 so CI fails
    exit 1
else
    echo "OpenAPI client is up to date."
fi

#!/usr/bin/env bash
# Run the Swift probe on a dedicated iOS simulator against the lane stack.
# Usage: run-simulator-tests.sh <evidence-json> [xcodebuild -only-testing args]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../stack/env.sh"
OUT="$(cd "$(dirname "$1")" 2>/dev/null && pwd || mkdir -p "$(dirname "$1")" && cd "$(dirname "$1")" && pwd)/$(basename "$1")"; shift
eval "$(native_auth_supabase status -o env 2>/dev/null)"
DEVICE_NAME="Argus Native Auth Proof"
UDID="$(xcrun simctl list devices -j | python3 -c "
import json,sys
for runtime in json.load(sys.stdin)['devices'].values():
    for d in runtime:
        if d['name'] == '$DEVICE_NAME' and d['isAvailable']: print(d['udid']); raise SystemExit
")"
if [ -z "$UDID" ]; then
  UDID="$(xcrun simctl create "$DEVICE_NAME" "iPhone 17 Pro" com.apple.CoreSimulator.SimRuntime.iOS-27-0)"
fi
xcrun simctl boot "$UDID" 2>/dev/null || true
export TEST_RUNNER_NATIVE_AUTH_ARGUS_API="http://127.0.0.1:$NATIVE_AUTH_API_PORT"
export TEST_RUNNER_NATIVE_AUTH_ADAPTER="http://127.0.0.1:$NATIVE_AUTH_ADAPTER_PORT"
export TEST_RUNNER_NATIVE_AUTH_SUPABASE_URL="$API_URL"
export TEST_RUNNER_NATIVE_AUTH_ANON_KEY="$ANON_KEY"
export TEST_RUNNER_NATIVE_AUTH_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY"
export TEST_RUNNER_NATIVE_AUTH_MAILPIT_URL="$MAILPIT_URL"
LOG="$NATIVE_AUTH_WORK/ios-test.log"
mkdir -p "$NATIVE_AUTH_WORK"
cd "$HERE/ArgusAuthProbeApp"
set +e
# Hosted in the probe app: Keychain writes fail in an unhosted test bundle.
xcodebuild test -project ArgusAuthProbeApp.xcodeproj -scheme ArgusAuthProbeApp -destination "id=$UDID" \
  -derivedDataPath "$NATIVE_AUTH_WORK/DerivedData" "$@" > "$LOG" 2>&1
STATUS=$?
set -e
python3 "$HERE/collect_results.py" "$LOG" "$OUT" "$UDID"
exit $STATUS

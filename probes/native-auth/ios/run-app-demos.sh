#!/usr/bin/env bash
# App-level demos on the probe simulator. Needs: lane stack in turnstile-pass
# mode (stack/restart-auth.sh turnstile-pass), Argus API, the Turnstile page
# server (python3 -m http.server 57462 in ios/turnstile), and a prior
# run-simulator-tests.sh build. Usage: run-app-demos.sh <evidence-dir>
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../stack/env.sh"
mkdir -p "$1"; OUT="$(cd "$1" && pwd)"
eval "$(native_auth_supabase status -o env 2>/dev/null)"
BUNDLE="local.argus.native-auth-proof"
APP="$NATIVE_AUTH_WORK/DerivedData/Build/Products/Debug-iphonesimulator/ArgusAuthProbeApp.app"
UDID="$(xcrun simctl list devices -j | python3 -c "
import json,sys
print(next(d['udid'] for ds in json.load(sys.stdin)['devices'].values() for d in ds if d['name']=='Argus Native Auth Proof'))")"
xcodebuild build -project "$HERE/ArgusAuthProbeApp/ArgusAuthProbeApp.xcodeproj" -scheme ArgusAuthProbeApp \
  -destination "id=$UDID" -derivedDataPath "$NATIVE_AUTH_WORK/DerivedData" -quiet
xcrun simctl install "$UDID" "$APP"
IP="10.$((RANDOM % 250 + 1)).$((RANDOM % 250 + 1)).9"

launch() {
  SIMCTL_CHILD_NATIVE_AUTH_ANON_KEY="$ANON_KEY" SIMCTL_CHILD_NATIVE_AUTH_SUPABASE_URL="$API_URL" \
  SIMCTL_CHILD_NATIVE_AUTH_ARGUS_API="http://127.0.0.1:$NATIVE_AUTH_API_PORT" \
  SIMCTL_CHILD_NATIVE_AUTH_DEVICE_IP="$IP" \
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE" "$@" > /dev/null
}
capture() {
  sleep "$2"
  xcrun simctl io "$UDID" screenshot "$OUT/$1.png" > /dev/null 2>&1
  cp "$(xcrun simctl get_app_container "$UDID" "$BUNDLE" data)/Documents/probe-log.json" "$OUT/$1.json"
}

launch -autorun turnstile -sitekey 1x00000000000000000000AA; capture turnstile-test-pass 15
launch -autorun turnstile -sitekey 2x00000000000000000000AB; capture turnstile-test-fail 15
launch -autorun turnstile -sitekey 3x00000000000000000000FF; capture turnstile-test-interactive 12

EMAIL="$(cd "$HERE/../http_probe" && API_URL="$API_URL" ANON_KEY="$ANON_KEY" SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  DB_URL="$DB_URL" MAILPIT_URL="$MAILPIT_URL" NATIVE_AUTH_ARGUS_API=unused \
  "$NATIVE_AUTH_ROOT/.venv/bin/python" -c "
from harness import Identities, Stack, run_id
print(Identities(Stack.from_env(), run_id()).create('app-recovery').email)")"
SENT="$(date +%s)"
launch -autorun recovery -recoveryEmail "$EMAIL"; sleep 12
CALLBACK="$(cd "$HERE/../http_probe" && API_URL="$API_URL" ANON_KEY="$ANON_KEY" SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  DB_URL="$DB_URL" MAILPIT_URL="$MAILPIT_URL" NATIVE_AUTH_ARGUS_API=unused \
  "$NATIVE_AUTH_ROOT/.venv/bin/python" -c "
from harness import GoTrue, Mailpit, Stack
s = Stack.from_env()
print(GoTrue(s).verify_link(Mailpit(s).latest_link('$EMAIL', after=$SENT)).headers['location'])")"
# iOS may ask "Open in ArgusAuthProbeApp?" before delivering a custom-scheme
# URL. Each delivery waits for the app to log its outcome before the next.
deliver() {
  local log before
  log="$(xcrun simctl get_app_container "$UDID" "$BUNDLE" data)/Documents/probe-log.json"
  count() { { grep -o callback.completed "$log" || true; } | wc -l; }
  before="$(count)"
  xcrun simctl openurl "$UDID" "$1"
  echo "If iOS asks \"Open in ArgusAuthProbeApp?\", tap Open ($2)."
  for _ in $(seq 1 90); do
    if [ "$(count)" -gt "$before" ]; then return; fi
    sleep 1
  done
  echo "no callback outcome for $2" >&2; exit 1
}
deliver "$CALLBACK" "issued code"
deliver "$CALLBACK" "same code again"
deliver "argusnativeproof://auth-callback?code=00000000-0000-0000-0000-000000000000" "forged code"
capture callback-delivery 2
echo "evidence in $OUT"

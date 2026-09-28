#!/usr/bin/env bash
# App-level demos on the probe simulator. Needs: lane stack in turnstile-pass
# mode (stack/restart-auth.sh turnstile-pass), Argus API, the Turnstile page
# server (python3 -m http.server 57462 in ios/turnstile), and a prior
# run-simulator-tests.sh build. Usage: run-app-demos.sh <evidence-root>
# Writes <evidence-root>/app/ and exits with the evidence gate's verdict.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../stack/env.sh"
mkdir -p "$1/app"; ROOT="$(cd "$1" && pwd)"; OUT="$ROOT/app"
eval "$(native_auth_supabase status -o env 2>/dev/null)"
BUNDLE="local.argus.native-auth-proof"
APP="$NATIVE_AUTH_WORK/DerivedData/Build/Products/Debug-iphonesimulator/ArgusAuthProbeApp.app"
UDID="$(xcrun simctl list devices -j | python3 -c "
import json,sys
print(next(d['udid'] for ds in json.load(sys.stdin)['devices'].values() for d in ds if d['name']=='Argus Native Auth Proof'))")"
xcodebuild build -project "$HERE/ArgusAuthProbeApp/ArgusAuthProbeApp.xcodeproj" -scheme ArgusAuthProbeApp \
  -destination "id=$UDID" -derivedDataPath "$NATIVE_AUTH_WORK/DerivedData" -quiet
# A reboot clears any system prompt left by an earlier run, so an old
# callback cannot reach this run.
xcrun simctl shutdown "$UDID" 2> /dev/null || true
xcrun simctl boot "$UDID"
xcrun simctl bootstatus "$UDID" -b > /dev/null
xcrun simctl install "$UDID" "$APP"
python3 - "$OUT/run.json" "$UDID" "$HERE/.." <<'PY'
import json, subprocess, sys
from datetime import datetime, timezone
out, udid, probes = sys.argv[1:4]
sys.path.insert(0, probes)
import evidence_gate
devices = json.loads(subprocess.run(["xcrun", "simctl", "list", "devices", "-j"], capture_output=True, text=True).stdout)["devices"]
runtime = next((k.rsplit(".", 1)[-1] for k, ds in devices.items() for d in ds if d["udid"] == udid), "unknown runtime")
record = {
    "client": "ArgusAuthProbeApp on iOS Simulator",
    "environment": f"simulator 'Argus Native Auth Proof', {runtime}; lane stack in turnstile-pass mode",
    "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    **evidence_gate.capture_identity(),
}
open(out, "w").write(json.dumps(record, indent=2) + "\n")
PY
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
app_log() { echo "$(xcrun simctl get_app_container "$UDID" "$BUNDLE" data)/Documents/probe-log.json"; }
# Waits up to $2 seconds for the app log to mention $1.
wait_for_log() {
  for _ in $(seq 1 "$2"); do
    if grep -q "\"$1\"" "$(app_log)" 2>/dev/null; then return; fi
    sleep 1
  done
  echo "app never logged $1" >&2; exit 1
}

# T3 and T4 run as a UI test, which taps Cancel without completing the
# challenge, so no person is needed. Screenshots come from outside the test.
UI_LOG="$NATIVE_AUTH_WORK/ui-test.log"
rm -f "$(app_log)"
(cd "$HERE/ArgusAuthProbeApp" && TEST_RUNNER_NATIVE_AUTH_ANON_KEY="$ANON_KEY" \
  TEST_RUNNER_NATIVE_AUTH_SUPABASE_URL="$API_URL" \
  TEST_RUNNER_NATIVE_AUTH_ARGUS_API="http://127.0.0.1:$NATIVE_AUTH_API_PORT" \
  xcodebuild test -project ArgusAuthProbeApp.xcodeproj -scheme ArgusAuthProbeUITests \
    -only-testing:ArgusAuthProbeUITests/CancelSecurityCheckUITests \
    -destination "id=$UDID" -derivedDataPath "$NATIVE_AUTH_WORK/DerivedData" \
    -collect-test-diagnostics never > "$UI_LOG" 2>&1) &
UI_TEST=$!
wait_for_log turnstile.interactive 300
sleep 3
xcrun simctl io "$UDID" screenshot "$OUT/turnstile-test-interactive.png" > /dev/null 2>&1
wait_for_log turnstile.cancelled 60
capture turnstile-cancelled 1
if ! wait "$UI_TEST" || ! grep -q "Executed 1 test, with 0 failures" "$UI_LOG"; then
  echo "cancel UI test failed; see $UI_LOG" >&2; exit 1
fi

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
# iOS asks "Open in ArgusAuthProbeApp?" on the first custom-scheme delivery to
# a new install. A UI test accepts every such prompt, as a user would.
PROMPT_LOG="$NATIVE_AUTH_WORK/ui-prompt.log"
(cd "$HERE/ArgusAuthProbeApp" && xcodebuild test -project ArgusAuthProbeApp.xcodeproj \
  -scheme ArgusAuthProbeUITests -only-testing:ArgusAuthProbeUITests/CustomSchemePromptUITests \
  -destination "id=$UDID" -derivedDataPath "$NATIVE_AUTH_WORK/DerivedData" \
  -collect-test-diagnostics never > "$PROMPT_LOG" 2>&1) &
PROMPTS=$!
sleep 45
deliver() {
  local before log
  log="$(app_log)"
  before="$({ grep -o callback.completed "$log" || true; } | wc -l)"
  xcrun simctl openurl "$UDID" "$1"
  sleep 2
  xcrun simctl io "$UDID" screenshot "$OUT/callback-delivery-$3.png" > /dev/null 2>&1
  for _ in $(seq 1 150); do
    if [ "$({ grep -o callback.completed "$log" || true; } | wc -l)" -gt "$before" ]; then return; fi
    sleep 1
  done
  echo "no callback outcome for $2" >&2; exit 1
}
deliver "$CALLBACK" "issued code" 1
deliver "$CALLBACK" "same code again" 2
deliver "argusnativeproof://auth-callback?code=00000000-0000-0000-0000-000000000000" "forged code" 3
if ! wait "$PROMPTS" || ! grep -q "Executed 1 test, with 0 failures" "$PROMPT_LOG"; then
  echo "scheme prompt UI test failed; see $PROMPT_LOG" >&2; exit 1
fi
ACCEPTED="$(sed -n 's/.*SCHEME_PROMPTS_ACCEPTED \([0-9][0-9]*\).*/\1/p' "$PROMPT_LOG" | tail -1)"
python3 - "$OUT/run.json" "${ACCEPTED:-unknown}" <<'PY'
import json, sys
path, accepted = sys.argv[1:3]
record = json.load(open(path))
record["scheme_prompts_accepted"] = accepted
open(path, "w").write(json.dumps(record, indent=2) + "\n")
PY
capture callback-delivery 2
exec python3 "$HERE/../evidence_gate.py" "$ROOT" --scope app

#!/usr/bin/env bash
# Run on one explicitly selected emulator and retain unedited captures on the host.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME to your SDK}"
: "${ANDROID_SERIAL:?Select a dedicated emulator, for example emulator-5580}"
if [[ $# != 1 ]]; then
  echo 'Usage: device-test.sh /absolute/output-directory' >&2
  exit 2
fi
OUTPUT_DIR="$1"
mkdir -p "$OUTPUT_DIR"
ADB="$ANDROID_HOME/platform-tools/adb"
"$ADB" -s "$ANDROID_SERIAL" install -r app/build/outputs/apk/debug/app-debug.apk
"$ADB" -s "$ANDROID_SERIAL" install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
"$ADB" -s "$ANDROID_SERIAL" shell am instrument -w \
  ai.argus.foundation.sample.test/androidx.test.runner.AndroidJUnitRunner | tee "$OUTPUT_DIR/instrumentation.txt"
"$ADB" -s "$ANDROID_SERIAL" pull \
  /sdcard/Android/data/ai.argus.foundation.sample/files/evidence "$OUTPUT_DIR/"
python3 - "$OUTPUT_DIR/instrumentation.txt" <<'PY'
import re
import sys
from pathlib import Path
output = Path(sys.argv[1]).read_text()
if not re.search(r'OK \(\d+ tests?\)', output) or 'FAILURES!!!' in output:
    raise SystemExit('Instrumentation did not report a passing test suite')
PY

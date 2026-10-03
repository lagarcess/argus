#!/bin/bash
# Mac pass for the Cuadrao design graft (#783, #785, #786 and PR 4 of 4).
# Checklist, expected differences and sign-off: docs/reports/evidence/784/README.md.
#
#   SIMULATOR_ID=<iPhone UDID> ios/scripts/cuadrao-design-mac-pass.sh [all|checks|tests|screens]
#
# checks   DesignPreviewTests state checks (xcrun swiftc, no simulator).
# tests    The design UI tests plus CuadraoHomeChartUITests, then their screenshot attachments.
# screens  Before/after launch screenshots: BASELINE (default 2185aefe) against this tree,
#          for a default launch and a --cuadrao-design launch, in light and dark.
#
# Output goes to ios/.build/mac-pass/<UTC stamp>/ (ignored by git). Nothing here signs,
# uploads or calls a backend; the default launch stays signed out.
set -euo pipefail

ios_dir="$(cd "$(dirname "$0")/.." && pwd)"
repo_dir="$(cd "$ios_dir/.." && pwd)"
step="${1:-all}"
baseline="${BASELINE:-2185aefe}"
settle="${SETTLE_SECONDS:-4}"
if [[ "$step" != all && "$step" != checks && "$step" != tests && "$step" != screens ]]; then
  echo "Usage: SIMULATOR_ID=<UDID> $0 [all|checks|tests|screens]" >&2
  exit 2
fi
if [[ "$step" != checks && -z "${SIMULATOR_ID:-}" ]]; then
  echo "Set SIMULATOR_ID from: xcrun simctl list devices available" >&2
  exit 2
fi
out="${OUT_DIR:-$ios_dir/.build/mac-pass/$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$out"
echo "Mac pass output: $out"

design_tests=(
  CuadraoHomeChartUITests
  CuadraoCollectionUITests CuadraoConsistencyUITests CuadraoContextUITests
  CuadraoGroupDesignUITests CuadraoHistoryDesignUITests CuadraoPlanCurrencyUITests
  CuadraoPlanDesignUITests CuadraoPolishUITests CuadraoProfileFollowupUITests
  CuadraoReceiptPermissionUITests CuadraoReceiptUITests CuadraoSupportUITests
  CuadraoVoiceDesignUITests
)

run_checks() {
  local runner
  for runner in run_home_balance run_plan_preview run_group_preview run_receipt_preview \
                run_temporary_chat run_avatar_crop; do
    echo "== $runner"
    python3 "$ios_dir/DesignPreviewTests/$runner.py"
  done 2>&1 | tee "$out/design-preview-checks.log"
}

run_tests() {
  local only=() name status=0 bundle
  for name in "${design_tests[@]}"; do only+=("-only-testing:ArgusFoundationUITests/$name"); done
  RESULT_DIR="$out/results" "$ios_dir/scripts/verify.sh" test "${only[@]}" || status=$?
  bundle="$(ls -dt "$out"/results/*.xcresult 2>/dev/null | head -1 || true)"
  if [[ -n "$bundle" ]]; then
    xcrun xcresulttool export attachments --path "$bundle" --output-path "$out/ui-attachments" \
      || echo "Could not export attachments; open $bundle in Xcode instead."
  fi
  return "$status"
}

prepare_simulator() {
  xcrun simctl boot "$SIMULATOR_ID" 2>/dev/null || true
  xcrun simctl bootstatus "$SIMULATOR_ID" -b >/dev/null
  xcrun simctl status_bar "$SIMULATOR_ID" override --time 9:41 --batteryState charged \
    --batteryLevel 100 --cellularBars 4 --wifiBars 3
}

# build_app <ios dir> <derived data dir>: prints the built .app path.
build_app() {
  xcodebuild build -project "$1/ArgusFoundation.xcodeproj" -scheme ArgusFoundation \
    -configuration Debug -destination "platform=iOS Simulator,id=$SIMULATOR_ID" \
    -derivedDataPath "$2" CODE_SIGNING_REQUIRED=NO >"$2.log" 2>&1
  find "$2/Build/Products/Debug-iphonesimulator" -maxdepth 1 -name '*.app' ! -name '*-Runner.app' | head -1
}

# install_app <.app>: clean install so no preview or appearance state carries over.
install_app() {
  bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Info.plist")"
  xcrun simctl uninstall "$SIMULATOR_ID" "$bundle_id" >/dev/null 2>&1 || true
  xcrun simctl install "$SIMULATOR_ID" "$1"
}

# shoot <name> <light|dark> [launch arguments...]
shoot() {
  local name="$1" look="$2"; shift 2
  xcrun simctl terminate "$SIMULATOR_ID" "$bundle_id" >/dev/null 2>&1 || true
  xcrun simctl ui "$SIMULATOR_ID" appearance "$look"
  xcrun simctl launch "$SIMULATOR_ID" "$bundle_id" "$@" >/dev/null
  sleep "$settle"
  xcrun simctl io "$SIMULATOR_ID" screenshot "$out/screens/$name.png" >/dev/null
  echo "  $name.png"
}

# The two launches compared before/after, in both appearances.
shoot_common() {
  local tag="$1" look
  for look in light dark; do
    shoot "$tag-default-$look" "$look"
    shoot "$tag-design-$look" "$look" --cuadrao-design -cuadrao.design.appearance "$look"
  done
}

run_screens() {
  local app look
  work="$(mktemp -d)/baseline-src"
  mkdir -p "$out/screens"
  prepare_simulator
  echo "== baseline $baseline"
  git -C "$repo_dir" worktree add --detach "$work" "$baseline" >/dev/null
  trap 'git -C "$repo_dir" worktree remove --force "$work" 2>/dev/null || true' EXIT
  app="$(build_app "$work/ios" "$out/baseline-build")"
  install_app "$app"
  shoot_common before
  git -C "$repo_dir" worktree remove --force "$work"; trap - EXIT
  echo "== this tree ($(git -C "$repo_dir" rev-parse --short HEAD))"
  app="$(build_app "$ios_dir" "$out/head-build")"
  install_app "$app"
  shoot_common after
  for look in light dark; do
    shoot "after-design-home-$look" "$look" --cuadrao-design --cuadrao-home --home-populated \
      -cuadrao.design.appearance "$look"
    shoot "after-design-gallery-$look" "$look" --cuadrao-design --design-gallery \
      -cuadrao.design.appearance "$look"
  done
  compare_pairs | tee "$out/screens/compare.txt"
}

compare_pairs() {
  local pair before after
  for pair in default-light default-dark design-light design-dark; do
    before="$out/screens/before-$pair.png"; after="$out/screens/after-$pair.png"
    if command -v compare >/dev/null; then
      printf '%s: %s differing pixels\n' "$pair" \
        "$(compare -metric AE "$before" "$after" "$out/screens/diff-$pair.png" 2>&1 || true)"
    elif cmp -s "$before" "$after"; then
      echo "$pair: identical files"
    else
      echo "$pair: files differ; compare by eye (install ImageMagick for a pixel count)"
    fi
  done
}

status=0
case "$step" in
  checks) run_checks ;;
  tests) run_tests || status=$? ;;
  screens) run_screens ;;
  all) run_checks; run_tests || status=$?; run_screens ;;
esac
echo "Mac pass output: $out"
exit "$status"

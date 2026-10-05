"""Verify Release overrides ignored developer flags in effective Xcode settings."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[2]
local = root / "ios/Config/Local.xcconfig"
if local.exists():
    raise SystemExit("Use an isolated checkout without Local.xcconfig")
try:
    local.write_text("ARGUS_APPLE_SIGN_IN_ENABLED = true\nARGUS_GOOGLE_SIGN_IN_ENABLED = true\n")
    result = subprocess.run([
        "xcodebuild", "-project", str(root / "ios/ArgusFoundation.xcodeproj"),
        "-scheme", "ArgusFoundation", "-configuration", "Release",
        "-showBuildSettings", "-json",
    ], check=True, capture_output=True, text=True)
    settings = next(entry["buildSettings"] for entry in json.loads(result.stdout)
                    if entry["target"] == "ArgusFoundation")
    for key in ["ARGUS_APPLE_SIGN_IN_ENABLED", "ARGUS_GOOGLE_SIGN_IN_ENABLED"]:
        if settings[key] != "false":
            raise SystemExit(f"Release unexpectedly enables {key}")
    print("Release effective settings passed 2 forced-off checks with local flags enabled")
finally:
    local.unlink(missing_ok=True)

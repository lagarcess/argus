"""Build/test with synthetic credentials in ignored test-runner configuration only."""

import argparse
import datetime
import json
import plistlib
import subprocess
from pathlib import Path

from local_stack import Allocation

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "ios/.build/auth-local"
DERIVED = ROOT / "ios/.build/DerivedData"
parser = argparse.ArgumentParser()
parser.add_argument("simulator")
parser.add_argument(
    "--only",
    default="ArgusFoundationUITests/AuthJourneyUITests/testRegisteredSessionSurvivesRelaunchAndSignsOut",
)
parser.add_argument("--captcha-mode", choices=["pass", "fail", "hold"], default="pass")
parser.add_argument("--accounts", action="store_true")
parser.add_argument("--language", choices=["en", "es-419"], default="en")
parser.add_argument("--appearance", choices=["light", "dark", "system"], default="light")
parser.add_argument("--port-base", type=int, default=58400)
parser.add_argument(
    "--response-loss-proxy",
    action="store_true",
    help="Opt in to local committed-response-loss acceptance; requires a build using the allocation's API fault-proxy port",
)
args = parser.parse_args()
allocation = Allocation(args.accounts, args.port_base)
WORK = allocation.work
DERIVED = DERIVED.with_name(DERIVED.name + allocation.suffix)
if args.simulator == "8B7975F1-1338-4966-90E2-770416CAF174":
    raise SystemExit("Refusing founder-owned simulator")
cfg = json.loads((WORK / "client.json").read_text())
if cfg["apiURL"] != allocation.url() + "/api/v1" or cfg["supabaseURL"] != allocation.url(
    1
):
    raise SystemExit("Fixture does not match this loopback allocation")
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
common = [
    "-destination",
    f"platform=iOS Simulator,id={args.simulator}",
    "-parallel-testing-enabled",
    "NO",
]
with (WORK / f"ui-build-{stamp}.log").open("w") as log:
    subprocess.run(
        [
            "xcodebuild",
            "build-for-testing",
            "-project",
            str(ROOT / "ios/ArgusFoundation.xcodeproj"),
            "-scheme",
            "ArgusFoundation",
            "-derivedDataPath",
            str(DERIVED),
            *common,
            "CODE_SIGNING_REQUIRED=NO",
        ],
        stdout=log,
        stderr=log,
        check=True,
    )
source = next((DERIVED / "Build/Products").glob("ArgusFoundation_*.xctestrun"))
settings = plistlib.loads(source.read_bytes())
targets = (
    [
        target
        for config in settings["TestConfigurations"]
        for target in config["TestTargets"]
    ]
    if "TestConfigurations" in settings
    else [value for key, value in settings.items() if not key.startswith("__")]
)
for target in targets:
    target.setdefault("EnvironmentVariables", {}).update(
        {
            "ARGUS_TEST_AUTH_UI_ENABLED": "true",
            "ARGUS_TEST_ACCOUNTS_UI_ENABLED": str(args.accounts).lower(),
            "ARGUS_TEST_LANGUAGE": args.language,
            "ARGUS_TEST_APPEARANCE": args.appearance,
            "ARGUS_TEST_RESPONSE_LOSS_PROXY": str(args.response_loss_proxy).lower(),
            "ARGUS_TEST_FAULT_URL": allocation.url(12) + "/__fault",
            "ARGUS_TEST_EMAIL_B": cfg["users"][1]["email"],
            "ARGUS_TEST_PASSWORD_B": cfg["users"][1]["password"],
            "ARGUS_TEST_EMAIL": cfg["users"][0]["email"],
            "ARGUS_TEST_PASSWORD": cfg["users"][0]["password"],
        }
    )
# Keep beside original because __TESTROOT__ paths are relative to this file.
runner = source.with_name(f"ios-auth-{stamp}.xctestrun")
runner.write_bytes(plistlib.dumps(settings))
runner.chmod(0o600)
result = WORK / f"ui-{stamp}.xcresult"
(WORK / "captcha-mode").write_text(args.captcha_mode)
try:
    with (WORK / f"ui-{stamp}.log").open("w") as log:
        completed = subprocess.run(
            [
                "xcodebuild",
                "test-without-building",
                "-collect-test-diagnostics",
                "never",
                "-xctestrun",
                str(runner),
                *common,
                "-resultBundlePath",
                str(result),
                f"-only-testing:{args.only}",
            ],
            stdout=log,
            stderr=log,
        )
    print(f"Native test exit={completed.returncode}; ignored result: {result.name}")
    raise SystemExit(completed.returncode)
finally:
    runner.unlink(missing_ok=True)
    (WORK / "captcha-mode").unlink(missing_ok=True)

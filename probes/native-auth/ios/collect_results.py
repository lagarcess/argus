"""Turn NATIVE_PROBE_RESULT lines from an xcodebuild log into evidence JSON."""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evidence_gate  # noqa: E402

log_path, out_path, udid = sys.argv[1:4]
log = Path(log_path).read_text(errors="replace")
# Keep every emitted line, repeats included, so the gate can reject them.
results = [
    json.loads(line.split("NATIVE_PROBE_RESULT ", 1)[1])
    for line in log.splitlines()
    if "NATIVE_PROBE_RESULT " in line
]
jwt = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
body = json.dumps(results)
if jwt.search(body):
    raise SystemExit("refusing to write evidence: a JWT-shaped value is present")
devices = json.loads(
    subprocess.run(
        ["xcrun", "simctl", "list", "devices", "-j"], capture_output=True, text=True
    ).stdout
)["devices"]
runtime = next(
    (
        key.rsplit(".", 1)[-1]
        for key, ds in devices.items()
        for d in ds
        if d["udid"] == udid
    ),
    "unknown runtime",
)
summary = re.findall(r"Executed \d+ tests?, with \d+ failures? .*", log)
xcode = subprocess.run(
    ["xcodebuild", "-version"], capture_output=True, text=True
).stdout.split("\n")[0]
Path(out_path).parent.mkdir(parents=True, exist_ok=True)
Path(out_path).write_text(
    json.dumps(
        {
            "client": "Swift ArgusNativeAuth (supabase-swift 2.55.2) XCTest hosted in ArgusAuthProbeApp on iOS Simulator",
            "environment": f"{xcode}; simulator 'Argus Native Auth Proof' (iPhone 17 Pro), {runtime}; lane stack argus-native-auth-proof",
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **evidence_gate.capture_identity(),
            "xcodebuild_summary": summary[-1] if summary else "missing",
            "results": sorted(
                results, key=lambda r: int(re.sub(r"\D", "", r["id"]) or 0)
            ),
        },
        indent=2,
    )
    + "\n"
)
for r in sorted(results, key=lambda r: r["id"]):
    print(f"[{r['verdict'].upper():4}] {r['id']} {r['scenario']}")
    if r["verdict"] != "pass":
        print(f"       observed={r['observed']}")
print(summary[-1] if summary else "no xcodebuild summary")
problems = evidence_gate.verify(Path(out_path).parent, "automated", [Path(out_path).name])
for problem in problems:
    print(f"EVIDENCE GATE: {problem}", file=sys.stderr)
sys.exit(1 if problems else 0)

"""Run an inspected Playwright driver without logging private input arguments.

The installed CLI owns the isolated browser. Inputs and raw results remain in
ignored QA storage until the controller has audited them for publication.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("driver", type=Path)
parser.add_argument("input", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--session", default="share-answer")
parser.add_argument("--cli", required=True, type=Path)
arguments = parser.parse_args()
code = arguments.driver.read_text().replace(
    "__QA_INPUT__", json.dumps(json.loads(arguments.input.read_text()))
)
result = subprocess.run(
    ["node", str(arguments.cli), f"-s={arguments.session}", "--raw", "run-code", code],
    capture_output=True,
    text=True,
    check=False,
)
arguments.output.write_text(result.stdout)
arguments.output.chmod(0o600)
if result.stderr:
    errors = arguments.output.with_suffix(".stderr")
    errors.write_text(result.stderr)
    errors.chmod(0o600)
failed = bool(result.returncode or result.stdout.startswith("### Error"))
print(
    json.dumps(
        {"exit_code": result.returncode, "driver_failed": failed, "result_saved": True}
    )
)
raise SystemExit(1 if failed else 0)

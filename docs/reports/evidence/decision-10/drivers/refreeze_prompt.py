"""Regenerate .agent/interpreter_prompt_fingerprint.json from the current tree
and point last_measured at the committed scorecard.
Usage: python refreeze_prompt.py <scorecard_path> <commit_sha>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from tests.interpreter_prompt_surface import FINGERPRINT_PATH, model_facing_surface  # noqa: E402

scorecard_path, commit = sys.argv[1:3]
totals = json.loads(Path(scorecard_path).read_text())["totals"]
fingerprint = json.loads(FINGERPRINT_PATH.read_text())
fingerprint["last_measured"] = {
    "commit": commit,
    "scorecard": scorecard_path,
    "passed": totals["passed"],
    "failed": totals["failed"],
}
fingerprint["surface"] = model_facing_surface(Path("."))
FINGERPRINT_PATH.write_text(json.dumps(fingerprint, indent=2) + "\n")
print("fingerprint refrozen at", commit, totals)

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/Users/garces/.codex/worktrees/aa72/private-alpha-next")
OUT = Path(__file__).resolve().parent
TARGET = "tests/memory/test_saved_decision_lifecycle.py::test_registered_default_off_proposal_creates_no_state"
BASELINE = "51086fda2014ddac2aba821a827c7b19234be779"
records = []
for name, mode, target in [
    ("local-dotenv", None, TARGET),
    ("explicit-disabled-file", "false", "tests/memory/test_saved_decision_lifecycle.py"),
    ("test-clears-enabled-flag", "true", TARGET),
]:
    env = os.environ.copy()
    env.pop("ARGUS_RUN_LIVE_EVALS", None)
    env.pop("REGISTRY_MEMORY_PROBE_CLEAR_AT_TEST", None)
    if mode is None:
        env.pop("ARGUS_ENABLE_PERSONALIZATION_MEMORY", None)
    else:
        env["ARGUS_ENABLE_PERSONALIZATION_MEMORY"] = mode
    if name == "test-clears-enabled-flag":
        env["REGISTRY_MEMORY_PROBE_CLEAR_AT_TEST"] = "1"
    env["PYTHONPATH"] = str(OUT) + os.pathsep + str(ROOT / "src") + os.pathsep + str(ROOT)
    command = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "--no-cov", "-q", "-s", "-p", "memory_flag_probe", target]
    proc = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
    log = OUT / (name + ".log")
    log.write_text(proc.stdout)
    summary = [line for line in proc.stdout.splitlines() if "MEMORY_FLAG_PROBE" in line or (" passed" in line or " failed" in line) and line.startswith("=")]
    records.append({"name":name,"command":command,"shell_flag":mode,"clear_flag_at_test_call":name == "test-clears-enabled-flag","returncode":proc.returncode,"log":str(log),"log_sha256":hashlib.sha256(log.read_bytes()).hexdigest(),"summary":summary})
    print(json.dumps(records[-1]), flush=True)
paths = ["src/argus/memory/service.py", "tests/memory/test_saved_decision_lifecycle.py", "tests/memory/conftest.py", "tests/conftest.py", "src/argus/env.py"]
proof = []
for owner in paths:
    current = (ROOT / owner).read_bytes()
    baseline = subprocess.check_output(["git", "show", BASELINE + ":" + owner], cwd=ROOT)
    proof.append({"path":owner,"candidate_sha256":hashlib.sha256(current).hexdigest(),"integration_sha256":hashlib.sha256(baseline).hexdigest(),"identical":current == baseline})
result = {"head_at_completion":subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,text=True).strip(),"integration":BASELINE,"owner_equality":proof,"local_dotenv_flag":{"file":".env","line":426,"value":"true"},"probes":records,"scope":"Read-only checkout; test plugin, logs and analysis only in /private/tmp. No live evals requested."}
(OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")

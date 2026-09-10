"""Copy committed web files into temporary QA storage; never edit app config."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dotenv import dotenv_values

root = Path.cwd()
out = Path(__file__).parent
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if sha != os.environ.get("READOUT_LIVE_SHA"):
    raise SystemExit("Exact committed SHA required")
if subprocess.check_output(["git", "status", "--porcelain", "--", "src", "web"], text=True).strip():
    raise SystemExit("Runtime source must be clean")
mirror = Path(tempfile.mkdtemp(prefix=f"argus-readout-live-{sha[:8]}-"))
files = subprocess.check_output(["git", "ls-files", "-z", "web", "src/argus/domain"], text=True).split("\0")
hashes = {}
for relative in files:
    if not relative or (not relative.startswith("web/") and not relative.endswith(".json")):
        continue
    source = root / relative
    if not source.is_file():
        continue
    target = mirror / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
(mirror / "web/node_modules").symlink_to(root / "web/node_modules", target_is_directory=True)
environment = dict(os.environ)
for p in [root / ".env", root / "web/.env.local"]:
    if p.exists():
        for key in dotenv_values(p):
            environment[key] = ""
for key in tuple(environment):
    if any(part in key.upper() for part in ("KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE", "SUPABASE", "POSTHOG", "ALPACA", "OPENROUTER")):
        environment[key] = ""
environment.update({"__NEXT_PROCESSED_ENV": "true", "NEXT_PUBLIC_MOCK_AUTH": "true", "NEXT_PUBLIC_ENABLE_SPANISH": "true", "NEXT_PUBLIC_ARGUS_API_URL": "http://127.0.0.1:8540/api/v1", "NEXT_PUBLIC_SUPABASE_URL": "", "NEXT_PUBLIC_SUPABASE_ANON_KEY": "", "NEXT_TELEMETRY_DISABLED": "1", "NEXT_DIST_DIR": ".next"})
(out / "web-source.json").write_text(json.dumps({"candidate_sha": sha, "temporary_web_root": str(mirror / "web"), "tracked_source_sha256": hashes, "environment_file_writes": 0}, indent=2) + "\n")
print(json.dumps({"temporary_web_root": str(mirror / "web"), "source_file_count": len(hashes), "candidate_sha": sha}))
subprocess.run(["bun", "run", "dev", "--webpack", "--hostname", "127.0.0.1", "--port", "3220"], cwd=mirror / "web", env=environment, check=True)

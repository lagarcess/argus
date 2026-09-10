"""Run a credential-free temporary copy; never let Next write repository config."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--sha", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--api-port", type=int, default=8541)
parser.add_argument("--web-port", type=int, default=3221)
args = parser.parse_args()
root = Path.cwd()
if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != args.sha:
    raise SystemExit("Reader checkout must match --sha")
if subprocess.check_output(
    ["git", "status", "--porcelain", "--", "src", "web"], text=True
).strip():
    raise SystemExit("Reader runtime source must be clean")
if not (root / "web/node_modules").exists():
    raise SystemExit("Existing web dependencies required; this harness does not install")
mirror = Path(tempfile.mkdtemp(prefix=f"argus-final-writing-{args.sha[:8]}-"))
try:
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "web", "src/argus/domain"], text=True
    ).split("\0")
    hashes = {}
    for relative in files:
        if not relative or (
            not relative.startswith("web/") and not relative.endswith(".json")
        ):
            continue
        source = root / relative
        if not source.is_file() or source.name.startswith(".env"):
            continue
        target = mirror / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    (mirror / "web/node_modules").symlink_to(
        root / "web/node_modules", target_is_directory=True
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "SYSTEMROOT",
        }
    }
    environment.update(
        {
            "__NEXT_PROCESSED_ENV": "true",
            "NEXT_PUBLIC_MOCK_AUTH": "true",
            "NEXT_PUBLIC_ENABLE_SPANISH": "true",
            "NEXT_TELEMETRY_DISABLED": "1",
            "NEXT_PUBLIC_ARGUS_API_URL": f"http://127.0.0.1:{args.api_port}/api/v1",
            "NEXT_DIST_DIR": ".next",
        }
    )
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "reader_sha": args.sha,
        "temporary_web_root": str(mirror / "web"),
        "tracked_source_sha256": hashes,
        "environment_file_reads": 0,
        "environment_file_writes": 0,
        "temporary_copy_removed": False,
    }
    (args.output / "web-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps({"temporary_web_root": str(mirror / "web"), "reader_sha": args.sha}),
        flush=True,
    )
    subprocess.run(
        [
            "bun",
            "run",
            "dev",
            "--webpack",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(args.web_port),
        ],
        cwd=mirror / "web",
        env=environment,
        check=True,
    )
finally:
    shutil.rmtree(mirror)
    if "manifest" in locals():
        manifest["temporary_copy_removed"] = True
        (args.output / "web-source.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

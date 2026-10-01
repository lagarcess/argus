"""Reuse retained local financial services without changing their configuration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
BACKING = Path("/Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next")
WORK = ROOT / "ios/.build/accounts-local-59200"
RUNTIME = "/Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python"
API = "http://127.0.0.1:59300/api/v1"
SIMULATOR = "1A90F684-345F-465C-AA50-6A5298F34156"


def local_services():
    spec = importlib.util.spec_from_file_location(
        "assets_backing_stack", BACKING / "ios/scripts/auth/local_stack.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ALLOCATION = module.Allocation(True, 59200)
    cfg = module.status()
    dsn = urlsplit(cfg["DB_URL"])
    if (
        cfg["API_URL"] != "http://127.0.0.1:59201"
        or dsn.hostname != "127.0.0.1"
        or dsn.port != 59202
    ):
        raise SystemExit(
            "Refusing services outside the retained local financial allocation"
        )
    module.ROOT = ROOT
    module.status = lambda: cfg
    return module, cfg


def prepare():
    module, _ = local_services()
    WORK.mkdir(parents=True, exist_ok=True, mode=0o700)
    fixture = WORK / "client.json"
    if fixture.exists():
        print("Retained asset credentials already exist. No users or records changed.")
        return
    module.seed()
    cfg = json.loads(fixture.read_text())
    cfg["apiURL"] = API
    fixture.write_text(json.dumps(cfg))
    fixture.chmod(0o600)
    config = ROOT / "ios/Config/Local.xcconfig"
    value = config.read_text().replace(
        "http:/$()/127.0.0.1:59200", "http:/$()/127.0.0.1:59300"
    )
    value = value.replace("http:/$()/127.0.0.1:59205", "http:/$()/127.0.0.1:59305")
    config.write_text(value + "ARGUS_LOCAL_BUNDLE_IDENTIFIER = local.argus.assets-demo\n")
    print(
        "Prepared two synthetic asset owners and a separate native bundle. Prior demos remain unchanged."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "api"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
        return
    module, _ = local_services()
    module.ALLOCATION = module.Allocation(True, 59300)
    module.api(RUNTIME, accounts_enabled=True)


if __name__ == "__main__":
    main()

"""Run one native-auth probe suite and write sanitized evidence JSON."""

from __future__ import annotations

import argparse
import importlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from harness import Identities, Recorder, Stack, run_id

SUITES = {
    "session": "session_suite",
    "guest": "guest_suite",
    "guest-adapter": "adapter_suite",
    "captcha": "captcha_suite",
    "callbacks": "callback_suite",
}
REPO = Path(__file__).resolve().parents[3]


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=SUITES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--skip-expiry-wait", action="store_true")
    parser.add_argument("--captcha-mode", default="off")
    args = parser.parse_args()

    stack = Stack.from_env()
    ids = Identities(stack, run_id())
    rec = Recorder(client="python-httpx language-neutral probe (not a native client)")
    module = importlib.import_module(SUITES[args.suite])
    options = {
        "wait_for_expiry": not args.skip_expiry_wait,
        "captcha_mode": args.captcha_mode,
    }
    module.run(
        stack,
        ids,
        rec,
        **{k: v for k, v in options.items() if k in module.run.__code__.co_varnames},
    )
    rec.write(
        args.out,
        {
            "suite": args.suite,
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "argus_source_head": git_head(),
            "environment": "local lane Supabase stack argus-native-auth-proof (jwt_expiry=60, confirmations on) + unchanged Argus API",
        },
    )
    failed = [r.id for r in rec.results if r.verdict == "fail"]
    print(f"{len(rec.results)} checks, {len(failed)} failed {failed}")


if __name__ == "__main__":
    main()

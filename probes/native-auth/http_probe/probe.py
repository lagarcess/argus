"""Run one native-auth probe suite and write sanitized evidence JSON."""

from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evidence_gate  # noqa: E402
from harness import Identities, Recorder, Stack, run_id  # noqa: E402

SUITES = {
    "session": "session_suite",
    "guest": "guest_suite",
    "guest-adapter": "adapter_suite",
    "captcha": "captcha_suite",
    "callbacks": "callback_suite",
}


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
            **evidence_gate.capture_identity(),
            "environment": "local lane Supabase stack argus-native-auth-proof (jwt_expiry=60, confirmations on) + unchanged Argus API",
        },
    )
    failed = [r.id for r in rec.results if r.verdict == "fail"]
    print(f"{len(rec.results)} checks, {len(failed)} failed {failed}")
    problems = evidence_gate.verify(args.out.parent, "automated", [args.out.name])
    for problem in problems:
        print(f"EVIDENCE GATE: {problem}", file=sys.stderr)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

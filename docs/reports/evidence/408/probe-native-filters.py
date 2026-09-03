"""Send four labeled synthetic events through the real Argus capture path.

Run from the repository root with an explicit --env-file and --output. This
contacts PostHog only; no provider calls, Supabase writes, or product traffic.
The output omits credentials and contains only the synthetic event properties.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise SystemExit("Capture evidence requires a clean worktree")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    environment = f"validation_issue_408_{sha[:12]}_{stamp}"
    load_dotenv(args.env_file, override=True)
    os.environ["APP_ENV"] = environment

    from argus.api import state as api_state
    from argus.api.chat.research_evidence import record_research_turn_evidence
    from argus.observability import envelope as events
    from argus.observability.guest_funnel import capture_guest_funnel_event

    assert api_state.supabase_gateway is None, "Probe must not connect to Supabase"
    assert events.live_analytics_sink_enabled(), "PostHog capture must be configured"
    captured: list[dict[str, Any]] = []
    original_post = events.httpx.post

    def capture_post(url: str, *, json: dict[str, Any], timeout: float) -> Any:
        response = original_post(url, json=json, timeout=timeout)
        response.raise_for_status()
        captured.append({key: value for key, value in json.items() if key != "api_key"})
        return response

    events.httpx.post = capture_post
    try:
        for capability_class, degraded in (
            ("balanced_lookup", True),
            ("balanced_lookup", False),
            ("screening", False),
        ):
            record_research_turn_evidence(
                research={
                    "capability_class": capability_class,
                    "shape": "balanced",
                    "usage": {"cache_status": "bypass"},
                    **(
                        {"degraded": {"code": "research_unavailable"}} if degraded else {}
                    ),
                },
                user_id=f"{environment}:{capability_class}",
                conversation_id=None,
                message_id=None,
                request_id=None,
            )
        capture_guest_funnel_event(
            "guest_limit_reached",
            user_id=f"{environment}:guest",
            product_capability="chat",
        )
    finally:
        events.httpx.post = original_post
    source_paths = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "c7802b37f39772a1216514e37fb6ff2b63142181",
            "--",
            "src/",
        ],
        text=True,
    ).splitlines()
    result = {
        "evidence_kind": "synthetic_native_filter_probe_not_production_traffic",
        "candidate_sha": sha,
        "environment": environment,
        "source_sha256": {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in source_paths
        },
        "captured_events": captured,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    assert len(captured) == 4, "Every synthetic event must reach the capture endpoint"
    print(
        json.dumps(
            {"candidate_sha": sha, "environment": environment, "events": len(captured)}
        )
    )


if __name__ == "__main__":
    main()

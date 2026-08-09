#!/usr/bin/env python3
"""Resolve one coherent deployed SHA from Render status payloads."""

from __future__ import annotations

import argparse
import sys


def _status_values(raw_status: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw_status.splitlines():
        key, separator, value = line.partition("=")
        if separator and key and key not in values:
            values[key] = value
    return values


def _value(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    return "" if value == "<missing>" else value


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def resolve_deployed_sha(
    *, api_status: str, web_status: str, workflow_status: str, cron_status: str
) -> str:
    api = _status_values(api_status)
    web = _status_values(web_status)
    workflow = _status_values(workflow_status)
    cron = _status_values(cron_status)

    _require(_value(api, "status") == "live", "api_deploy_not_live")
    _require(_value(web, "status") == "live", "web_deploy_not_live")
    _require(_value(workflow, "status") == "ready", "workflow_version_not_ready")

    workflow_version_id = _value(workflow, "workflow_version_id")
    _require(
        workflow_version_id
        and workflow_version_id == _value(workflow, "expected_workflow_version_id"),
        "workflow_version_id_mismatch",
    )

    api_sha = _value(api, "commit")
    web_sha = _value(web, "commit")
    workflow_sha = _value(workflow, "commit")
    _require(api_sha and api_sha == web_sha, "api_web_deploy_sha_mismatch")
    _require(api_sha == workflow_sha, "workflow_commit_mismatch")

    # The cron holds the service-role key and deletes rows, so it may never lag
    # the surfaces the canary certifies. "absent" is read back from Render and
    # means nothing destructive is deployed, which is the one safe exception.
    # A lookup that failed is not absent and must never take that exception.
    cron_state = _value(cron, "status")
    _require(cron_state not in {"", "lookup_failed"}, "cron_status_unavailable")
    if cron_state != "absent":
        _require(cron_state == "live", "cron_deploy_not_live")
        _require(api_sha == _value(cron, "commit"), "cron_commit_mismatch")
    return api_sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-status", required=True)
    parser.add_argument("--web-status", required=True)
    parser.add_argument("--workflow-status", required=True)
    parser.add_argument("--cron-status", required=True)
    args = parser.parse_args()
    try:
        print(
            resolve_deployed_sha(
                api_status=args.api_status,
                web_status=args.web_status,
                workflow_status=args.workflow_status,
                cron_status=args.cron_status,
            )
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

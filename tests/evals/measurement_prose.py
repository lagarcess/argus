"""Prose rubric and availability evidence; provider receipts own availability."""

from __future__ import annotations

import json
from typing import Any

from tests.evals.prose_evidence import judged_prose_evidence

PROSE_JUDGE_RUBRIC_VERSION = "argus-prose-quality-v2"
PROSE_JUDGE_RUBRIC = """
Version: argus-prose-quality-v2

Judge only the prose qualities listed in the case. Do not grade asset symbols,
dates, strategy type, benchmark, stage outcome, or executable capability truth;
those are checked by typed assertions outside this judge.

The reply is not the whole screen. rendered_beside_reply is the complete list
of what the interface renders next to the assistant text on the same turn:
discovery rows with their source list, pressable recovery options, and
follow-up experiment rows. Voiced prose often only frames that surface, so
judge each claim against the prose and the rendered surface together: a
sentence that introduces or summarizes rows, sources, or options rendered
beside it is supported by them, and a claim that neither the prose nor the
rendered surface supports is still unsupported. An empty rendered_beside_reply
is not missing data; it means the interface rendered nothing beside the prose,
so a reply that presents results or options as delivered when neither the
prose nor the rendered surface contains them is unsupported.

Allowed prose criteria:
- recovery_tone: the user is not blamed, and the response keeps the idea usable.
- honesty: unsupported or uncertain capability is not presented as executable.
- spanish_language_integrity: Spanish sessions do not leak English fallback copy.
- no_raw_runtime_error: provider, Python, traceback, enum, or schema details are
  not exposed as user-facing recovery text.

Return JSON only. Use failed_criteria for any failed requested criterion.
"""


def composer_unavailability(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # A failed primary followed by usable prose is still quality-measurable.
    # JSON-schema calls (including the judge) are not the runtime prose composer.
    attempts = [
        index
        for index, receipt in enumerate(receipts)
        if receipt.get("task") == "chat_composer" and receipt.get("mode") == "chat_model"
    ]
    if not attempts or any(
        receipts[index].get("outcome") == "succeeded" for index in attempts
    ):
        return []
    if not all(
        receipts[index].get("outcome") in {"failed", "skipped"} for index in attempts
    ):
        return []
    return [
        {
            "component": "runtime_composer",
            "code": "provider_unavailable",
            "route_receipt_indices": attempts,
        }
    ]


def unavailable_prose_result(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "pass": None,
        "failed_criteria": [],
        "notes": reason,
        "rubric_version": PROSE_JUDGE_RUBRIC_VERSION,
    }


def retain_prose_context(
    result: dict[str, Any],
    *,
    criteria: tuple[str, ...],
    text: str,
    rendered_surface: dict[str, Any],
) -> None:
    prefix = "observed" if result.get("status") == "unavailable" else "judged"
    result["requested_criteria"] = list(criteria)
    result[f"{prefix}_assistant_text"] = judged_prose_evidence(text)
    result[f"{prefix}_rendered_context"] = judged_prose_evidence(
        json.dumps(rendered_surface, sort_keys=True)
    )

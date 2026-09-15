"""Prose rubric and availability evidence; provider receipts own availability."""

from __future__ import annotations

import json
from typing import Any

from tests.evals.prose_evidence import judged_prose_evidence

PROSE_JUDGE_RUBRIC_VERSION = "argus-prose-quality-v4"
PROSE_JUDGE_RUBRIC = """
Version: argus-prose-quality-v4

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
- scenario_framing: a forward-looking or valuation answer gives labeled
  scenarios or ranges built from cited inputs with the arithmetic shown, never
  a single number as the future, and no buy, sell, or hold advice.

- calculation_consistency: the reply states the result the displayed calculation
  computed, with the same units, currency, time basis and assumptions. It does
  not ask again for an input already supplied or claim a stored figure is absent.
  Acknowledging inputs without stating the computed result fails. Do not reward
  correct prose arithmetic if it contradicts or substitutes for the shown card.
- comparison_without_selection: when personal facts needed to compare products
  are absent, name useful comparison dimensions and the missing personal facts.
  Do not select, recommend, rank as best, or call any named product a fit for this
  reader, even after acknowledging uncertainty. Examples of dimensions are fees,
  eligibility, spending categories, repayment behavior and usable rewards.
- goal_currency_risk: reason from the spending goal stated in the current prompt.
  Savings in currency A funding a fixed expense in currency B lose purchasing
  power when B appreciates against A, equivalently when A depreciates against B.
  Matching the savings to B removes that currency mismatch. Do not reverse the
  adverse move or carry forward a replaced spending goal.
- drawdown_then_stop: present the asset's historical maximum drawdown and its
  actual observed window from the displayed Argus calculation. If the user named
  only a broad asset class such as crypto, identify the asset used and explicitly
  label it as a representative example, not a loss for the whole asset class.
  Make clear that
  it is a historical loss, not a future forecast. Then stop; do not replace the
  computation with a general risk essay, product choice or further interrogation.
- prior_answer_explanation: explain the earlier answer in simpler words while
  preserving its meaning and the direction of any comparison. Do not replace
  that explanation with a new market lookup or invent a new fact.

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
            "code": (
                "runtime_timeout"
                if any(
                    receipts[index].get("failure_mode")
                    in {"TimeoutError", "CancelledError"}
                    for index in attempts
                )
                else "provider_unavailable"
            ),
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

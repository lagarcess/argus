from __future__ import annotations

from typing import Any

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import (
    ConfirmationPayload,
    FinalResponsePayload,
    ResponseProfile,
    RunState,
)


def explain_stage(*, state: RunState) -> StageResult:
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    profile = _response_profile(state)
    strategy = _strategy_payload(state)
    optional_parameters = _optional_parameters(state)
    thesis = _thesis(strategy)
    assumption_summary = _assumption_summary(
        optional_parameters=optional_parameters,
        explanation_context=explanation_context,
    )
    caveat = _caveat_summary(explanation_context)

    total_return, benchmark_return, same_period = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    if total_return is None or benchmark_return is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": _build_incomplete_result_response(
                    profile=profile,
                    thesis=thesis,
                    assumption_summary=assumption_summary,
                    caveat=caveat,
                )
            },
        )

    return StageResult(
        outcome="ready_to_respond",
        stage_patch={
            "assistant_response": _build_response(
                total_return=total_return,
                benchmark_return=benchmark_return,
                same_period=same_period,
                profile=profile,
                thesis=thesis,
                assumption_summary=assumption_summary,
                caveat=caveat,
            )
        },
    )


def _result_payload(state: RunState) -> dict[str, Any]:
    payload = state.final_response_payload
    if payload is None:
        return {}
    if isinstance(payload, FinalResponsePayload):
        return dict(payload.result or {})
    if isinstance(payload, dict):
        return dict(payload.get("result") or {})
    return {}


def _explanation_context(state: RunState) -> dict[str, Any]:
    payload = state.final_response_payload
    if payload is None:
        return {}
    if isinstance(payload, FinalResponsePayload):
        return dict(payload.explanation_context or {})
    if isinstance(payload, dict):
        return dict(payload.get("explanation_context") or {})
    return {}


def _response_profile(state: RunState) -> ResponseProfile | None:
    return state.effective_response_profile


def _strategy_payload(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.strategy.model_dump(mode="python")
    strategy = payload.get("strategy") if isinstance(payload, dict) else None
    if isinstance(strategy, dict):
        return dict(strategy)
    return {}


def _optional_parameters(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.optional_parameters
    if isinstance(payload, dict):
        optional_parameters = payload.get("optional_parameters")
        if isinstance(optional_parameters, dict):
            return dict(optional_parameters)
    return {}


def _thesis(strategy: dict[str, Any]) -> str | None:
    thesis = strategy.get("strategy_thesis")
    if thesis is None:
        return None
    thesis_text = str(thesis).strip().rstrip(".")
    return thesis_text or None


def _assumption_summary(
    *,
    optional_parameters: dict[str, Any],
    explanation_context: dict[str, Any],
) -> str:
    defaulted_labels: list[str] = []
    user_labels: list[str] = []
    assumptions = explanation_context.get("assumptions", [])

    for value in optional_parameters.values():
        if not isinstance(value, dict):
            continue
        label = str(value.get("label") or "Unnamed setting")
        source = str(value.get("source") or "")
        if source == "default":
            defaulted_labels.append(label)
        elif source == "user":
            user_labels.append(label)

    parts = []
    if isinstance(assumptions, list) and assumptions:
        assumption_text = _compact_sentence_list(assumptions, limit=3)
        if assumption_text:
            parts.append("Assumptions: " + assumption_text)
    elif defaulted_labels:
        parts.append("Defaults: " + ", ".join(defaulted_labels) + ".")
    if user_labels:
        parts.append("User-set options: " + ", ".join(user_labels) + ".")
    return " ".join(parts)


def _caveat_summary(explanation_context: dict[str, Any]) -> str:
    caveats = explanation_context.get("caveats", [])
    if not isinstance(caveats, list) or not caveats:
        return "This is a return comparison, not causal attribution."
    caveat_text = _compact_sentence_list(caveats, limit=2)
    if not caveat_text:
        return "This is a return comparison, not causal attribution."
    return f"This is a return comparison, not causal attribution. {caveat_text}"


def _build_response(
    *,
    total_return: float,
    benchmark_return: float,
    same_period: bool,
    profile: ResponseProfile | None,
    thesis: str | None,
    assumption_summary: str,
    caveat: str,
) -> str:
    tone = profile.effective_tone if profile is not None else "friendly"
    verbosity = profile.effective_verbosity if profile is not None else "medium"
    expertise_mode = (
        profile.effective_expertise_mode if profile is not None else "beginner"
    )

    comparison_sentence = (
        f"Your strategy returned {total_return:.1f}% versus {benchmark_return:.1f}% "
        f"{_benchmark_scope_phrase(same_period)}."
    )
    thesis_sentence = (
        f"I tested: {thesis}."
        if thesis is not None
        else "I tested the confirmed strategy."
    )
    expertise_sentence = _expertise_sentence(expertise_mode)
    assumption_sentence = (
        f" {assumption_summary}" if assumption_summary else ""
    )

    if verbosity == "low":
        return (
            f"{comparison_sentence} {thesis_sentence} "
            f"{expertise_sentence}{assumption_sentence} Caveat: {caveat}"
        )

    tone_prefix = _tone_result_prefix(tone)
    if verbosity == "high":
        return (
            f"{tone_prefix}{comparison_sentence} {thesis_sentence} {expertise_sentence}"
            f"{assumption_sentence} Caveat: {caveat}"
        )

    return (
        f"{tone_prefix}{comparison_sentence} {thesis_sentence} {expertise_sentence}"
        f"{assumption_sentence} Caveat: {caveat}"
    )


def _tone_result_prefix(tone: str) -> str:
    if tone == "friendly":
        return "Here is the readout. "
    return ""


def _expertise_sentence(expertise_mode: str) -> str:
    if expertise_mode == "advanced":
        return "This is a return comparison only, without causal attribution."
    if expertise_mode == "intermediate":
        return "Use this as a direct benchmark comparison before deciding on refinements."
    return "This gives a simple benchmark comparison for the confirmed idea."


def _benchmark_scope_phrase(same_period: bool) -> str:
    if same_period:
        return "for the benchmark over the same period"
    return "for the reported benchmark"


def _build_incomplete_result_response(
    *,
    profile: ResponseProfile | None,
    thesis: str | None,
    assumption_summary: str,
    caveat: str,
) -> str:
    tone = profile.effective_tone if profile is not None else "friendly"
    verbosity = profile.effective_verbosity if profile is not None else "medium"
    expertise_mode = (
        profile.effective_expertise_mode if profile is not None else "beginner"
    )
    thesis_sentence = (
        f"This applies to your thesis: {thesis}."
        if thesis is not None
        else "This applies to the confirmed strategy."
    )
    expertise_sentence = _expertise_sentence(expertise_mode)
    base = (
        "The result payload is incomplete, so I cannot report observed returns yet. "
        f"{thesis_sentence} {expertise_sentence}"
    )
    if verbosity == "high":
        if tone == "friendly":
            return f"Here is the current status. {base} Assumptions and caveats: {assumption_summary} {caveat}"
        return f"{base} Assumptions and caveats: {assumption_summary} {caveat}"
    if verbosity == "low":
        return f"{base} Caveat: {assumption_summary} {caveat}"
    if tone == "concise":
        return f"{base} Caveat: {assumption_summary} {caveat}"
    return f"{base} Assumptions and caveat: {assumption_summary} {caveat}"


def _compact_sentence_list(values: list[Any], *, limit: int) -> str:
    sentences: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        text = " ".join(text.split())
        if len(text) > 140:
            text = text[:137].rstrip() + "..."
        if not text.endswith((".", "!", "?")):
            text += "."
        sentences.append(text)
        if len(sentences) >= limit:
            break
    return " ".join(sentences)


def _percent(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value) * 100
    except (TypeError, ValueError):
        return None


def _resolved_return_metrics(
    *,
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> tuple[float | None, float | None, bool]:
    metrics = explanation_context.get("metrics", {})
    benchmark_metrics = explanation_context.get("benchmark_metrics", {})
    total_return_pct = _nested_number(
        metrics,
        ("aggregate", "performance", "total_return_pct"),
    )
    if total_return_pct is None:
        total_return_pct = _nested_number(metrics, ("total_return_pct",))

    benchmark_return_pct = _nested_number(
        benchmark_metrics,
        ("aggregate", "total_return_pct"),
    )
    if benchmark_return_pct is None:
        benchmark_return_pct = _nested_number(
            benchmark_metrics,
            ("benchmark_return_pct",),
        )

    if total_return_pct is not None and benchmark_return_pct is not None:
        same_period = bool(
            explanation_context.get("comparable_same_period")
            or result_payload.get("comparable_same_period")
        )
        return total_return_pct, benchmark_return_pct, same_period

    return (
        _percent(result_payload.get("total_return")),
        _percent(result_payload.get("benchmark_return")),
        bool(result_payload.get("comparable_same_period")),
    )


def _nested_number(payload: Any, path: tuple[str, ...]) -> float | None:
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    try:
        if current is None or current == "":
            return None
        return float(current)
    except (TypeError, ValueError):
        return None

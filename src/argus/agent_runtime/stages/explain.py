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
    profile = _response_profile(state)
    strategy = _strategy_payload(state)
    optional_parameters = _optional_parameters(state)
    thesis = _thesis(strategy)
    assumption_summary = _assumption_summary(optional_parameters)
    caveat = (
        "This summarizes the observed returns versus the reported benchmark; "
        "it does not explain why performance differed."
    )

    total_return = _percent(result_payload.get("total_return"))
    benchmark_return = _percent(result_payload.get("benchmark_return"))
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
                result_payload=result_payload,
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
    thesis_text = str(thesis).strip()
    return thesis_text or None


def _assumption_summary(optional_parameters: dict[str, Any]) -> str:
    defaulted_labels: list[str] = []
    user_labels: list[str] = []

    for value in optional_parameters.values():
        if not isinstance(value, dict):
            continue
        label = str(value.get("label") or "Unnamed setting")
        source = str(value.get("source") or "")
        if source == "default":
            defaulted_labels.append(label)
        elif source == "user":
            user_labels.append(label)

    parts = ["Benchmark comparison reflects the result payload that was returned."]
    if defaulted_labels:
        parts.append("Defaults used: " + ", ".join(defaulted_labels) + ".")
    if user_labels:
        parts.append("User-set options: " + ", ".join(user_labels) + ".")
    return " ".join(parts)


def _build_response(
    *,
    total_return: float,
    benchmark_return: float,
    result_payload: dict[str, Any],
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
        f"{_benchmark_scope_phrase(result_payload)}."
    )
    thesis_sentence = (
        f"This result applies to your thesis: {thesis}."
        if thesis is not None
        else "This result applies to the confirmed strategy."
    )
    expertise_sentence = _expertise_sentence(expertise_mode)

    if verbosity == "low":
        if tone == "concise":
            return (
                f"{comparison_sentence} {thesis_sentence} "
                f"{expertise_sentence} Caveat: {assumption_summary}"
            )
        return (
            f"{comparison_sentence} {thesis_sentence} "
            f"{expertise_sentence} Caveat: {assumption_summary}"
        )

    if verbosity == "high":
        if tone == "friendly":
            return (
                f"Here is the confirmed result. {comparison_sentence} "
                f"{thesis_sentence} {expertise_sentence} "
                f"Assumptions and caveats: {assumption_summary} {caveat}"
            )
        return (
            f"{comparison_sentence} {thesis_sentence} {expertise_sentence} "
            f"Assumptions and caveats: {assumption_summary} {caveat}"
        )

    if tone == "concise":
        return (
            f"{comparison_sentence} {thesis_sentence} "
            f"{expertise_sentence} Caveat: {assumption_summary}"
        )
    return (
        f"{comparison_sentence} {thesis_sentence} {expertise_sentence} "
        f"Assumptions and caveat: {assumption_summary}"
    )


def _expertise_sentence(expertise_mode: str) -> str:
    if expertise_mode == "advanced":
        return "This is a return comparison only, without causal attribution."
    if expertise_mode == "intermediate":
        return "Use this as a direct benchmark comparison before deciding on refinements."
    return "This gives a simple benchmark comparison for the confirmed idea."


def _benchmark_scope_phrase(result_payload: dict[str, Any]) -> str:
    if bool(result_payload.get("comparable_same_period")):
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
        return f"{base} Caveat: {assumption_summary}"
    if tone == "concise":
        return f"{base} Caveat: {assumption_summary}"
    return f"{base} Assumptions and caveat: {assumption_summary}"


def _percent(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value) * 100
    except (TypeError, ValueError):
        return None

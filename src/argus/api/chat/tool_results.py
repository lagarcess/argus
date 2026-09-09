"""Publication of typed tool cards, separate from immutable backtest runs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from argus.api.chat.streaming import runtime_result_card, runtime_result_message
from argus.domain.tool_contracts import ToolResultCard


class ToolExecutionEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool_name: str
    artifact_id: str
    stage_patch: dict[str, Any]


@dataclass(frozen=True)
class ToolPublication:
    cards: list[dict[str, Any]]
    effects: list[ToolExecutionEffect]
    result_card: dict[str, Any] | None
    backtest_job: dict[str, Any] | None
    assistant_text: str | None


def prepare_runtime_tool_publication(
    runtime_result: dict[str, Any],
    effects: object,
    *,
    assistant_text: str | None,
    user_id: str,
    conversation_id: str,
    request_message_id: str | None,
    request_id: str | None,
) -> ToolPublication:
    """Resolve ordered tool effects and the existing single-job projection."""
    from argus.api.chat.research_jobs import apply_research_job_request

    cards = runtime_tool_result_cards(runtime_result)
    parsed = apply_runtime_tool_effects(
        runtime_result,
        effects,
        user_id=user_id,
        conversation_id=conversation_id,
        request_message_id=request_message_id,
        request_id=request_id,
    )
    if parsed:
        cards = runtime_tool_result_cards(runtime_result)
        assistant_text = runtime_result_message(runtime_result)
    result_card = runtime_result_card(runtime_result)
    backtest_job = runtime_result.get("backtest_job")
    final = runtime_result.get("final_response_payload")
    if not isinstance(backtest_job, dict) and isinstance(final, dict):
        backtest_job = final.get("backtest_job")
    backtest_job = dict(backtest_job) if isinstance(backtest_job, dict) else None
    if backtest_job is None and "research_job_request" in runtime_result:
        backtest_job = apply_research_job_request(
            runtime_result,
            user_id=user_id,
            conversation_id=conversation_id,
            request_message_id=request_message_id,
            request_id=request_id,
        )
        if backtest_job is None:
            assistant_text = runtime_result.get("assistant_response")
    if result_card is not None:
        result_card = bind_runtime_run_card(result_card, cards=cards, effects=parsed)
    return ToolPublication(cards, parsed, result_card, backtest_job, assistant_text)


def bind_runtime_run_card(
    result_card: dict[str, Any],
    *,
    cards: list[dict[str, Any]],
    effects: list[ToolExecutionEffect],
) -> dict[str, Any]:
    """Attach only the declared calls that produced this legacy run projection."""
    run_call_ids = {
        effect.call_id
        for effect in effects
        if isinstance(effect.stage_patch.get("final_response_payload"), dict)
        and isinstance(
            effect.stage_patch["final_response_payload"].get("result_card"), dict
        )
    }
    bound = [card for card in cards if card["call_id"] in run_call_ids]
    return {**result_card, "tool_result_cards": bound} if bound else result_card


def apply_runtime_tool_effects(
    runtime_result: dict[str, Any],
    effects: object,
    *,
    user_id: str,
    conversation_id: str,
    request_message_id: str | None,
    request_id: str | None,
) -> list[ToolExecutionEffect]:
    """Apply every declared call's private publication effect in execution order."""
    from argus.api.chat.research_jobs import apply_research_job_request

    if effects is None:
        return []
    if not isinstance(effects, list):
        raise ValueError("Tool effects must be an ordered list")
    parsed = [ToolExecutionEffect.model_validate(effect) for effect in effects]
    if len({effect.call_id for effect in parsed}) != len(parsed):
        raise ValueError("Tool effects repeat a call identity")
    cards = {card.call_id: card for card in tool_cards_from_metadata(runtime_result)}
    # Validate the complete batch before any job dispatch can spend a provider call.
    for effect in parsed:
        card = cards.get(effect.call_id)
        if card is None or (card.tool_name, card.artifact_id) != (
            effect.tool_name,
            effect.artifact_id,
        ):
            raise ValueError("A tool effect has no matching result identity")
    if parsed:
        # The graph's legacy projection may also contain the last job request.
        # The ordered effects own publication, so it must never dispatch twice.
        runtime_result.pop("research_job_request", None)
    if len(parsed) > 1:
        for key in ("assistant_response", "research", "discovery", "next_experiments"):
            runtime_result.pop(key, None)
    jobs = []
    for effect in parsed:
        patch = effect.stage_patch
        if "research_job_request" in patch:
            card = cards[effect.call_id]
            job = apply_research_job_request(
                patch,
                user_id=user_id,
                conversation_id=conversation_id,
                request_message_id=request_message_id,
                request_id=request_id,
                tool_call_id=effect.call_id,
                tool_name=effect.tool_name,
                tool_artifact_id=effect.artifact_id,
                tool_arguments=card.arguments,
            )
            if job is not None:
                jobs.append(
                    {
                        "call_id": effect.call_id,
                        "tool_name": effect.tool_name,
                        "artifact_id": effect.artifact_id,
                        "job": job,
                    }
                )
        for revised in tool_cards_from_metadata(patch):
            if (revised.call_id, revised.artifact_id, revised.tool_name) != (
                effect.call_id,
                effect.artifact_id,
                effect.tool_name,
            ):
                raise ValueError("Tool completion changed the call identity")
            cards[revised.call_id] = revised
    documents = [card.model_dump(mode="json") for card in cards.values()]
    runtime_result["tool_result_cards"] = documents
    final = runtime_result.get("final_response_payload")
    if isinstance(final, dict):
        final["tool_result_cards"] = documents
    if jobs:
        runtime_result["tool_jobs"] = jobs
    # The old one-call sidecar remains a compatibility projection. Multiple
    # calls keep their own typed results and private evidence separately.
    if len(parsed) == 1:
        for key in ("assistant_response", "research", "discovery", "next_experiments"):
            if key in parsed[0].stage_patch:
                runtime_result[key] = parsed[0].stage_patch[key]
    return parsed


def tool_cards_from_metadata(metadata: Mapping[str, Any]) -> list[ToolResultCard]:
    raw = metadata.get("tool_result_cards", [])
    if not isinstance(raw, list):
        raise ValueError("Tool result cards must be an ordered list")
    cards = [ToolResultCard.model_validate(card) for card in raw]
    for field in ("call_id", "artifact_id"):
        values = [getattr(card, field) for card in cards]
        if len(values) != len(set(values)):
            raise ValueError(f"Tool results repeat {field}")
    return cards


def runtime_tool_result_cards(runtime_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate once, then use identical card facts for final delivery and storage."""
    final = runtime_result.get("final_response_payload")
    source = final if isinstance(final, Mapping) else runtime_result
    cards = tool_cards_from_metadata(source)
    documents = [card.model_dump(mode="json") for card in cards]
    if documents:
        runtime_result["tool_result_cards"] = documents
    return documents

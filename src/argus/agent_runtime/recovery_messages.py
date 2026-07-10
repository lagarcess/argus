from __future__ import annotations

from typing import Any, Literal

RecoveryMessageCode = Literal[
    "interpreter_unavailable",
    "assumption_edit_unapplied",
    "setup_change_unapplied",
    "confirmation_change_unapplied",
    "latest_result_followup_unavailable",
    "private_alpha_save_unavailable",
    "confirmation_action_guidance",
    "confirmation_action_missing_context",
    "confirmation_action_missing_identity",
    "confirmation_action_stale_card",
    "confirmation_action_stale_payload",
    "confirmation_state_lost",
    "confirmation_cancelled",
    "clarification_generation_unavailable",
    "result_refine_missing",
    "context_macro_recovery",
    "context_corporate_events_recovery",
    "context_market_movers_recovery",
    "context_market_movers_seed_recovery",
    "capability_answer_unavailable",
    "runtime_failure",
    "artifact_action_invalid_state",
    "artifact_action_retry_stale",
    "artifact_action_retry_missing_artifact_id",
    "artifact_action_retry_missing_payload",
    "artifact_action_retry_non_retryable",
    "artifact_action_retry_rebuilt_confirmation",
    "artifact_action_retry_inactive",
    "execution_data_unavailable",
]


RECOVERY_FALLBACK_MESSAGES: dict[RecoveryMessageCode, str] = {
    "interpreter_unavailable": (
        "I saved your message, but I could not turn it into a reliable test setup. "
        "Please retry in a moment."
    ),
    "assumption_edit_unapplied": (
        "I saved your reply, but I could not safely apply that assumption change, "
        "so I left the current idea unchanged. Please retry the change in a moment."
    ),
    "setup_change_unapplied": (
        "I still have the {setup_phrase} in this chat, but I could not safely apply "
        "that change. Please retry in a moment."
    ),
    "confirmation_change_unapplied": (
        "I still have the {setup_phrase} confirmation in this chat, but I could not "
        "safely apply that change. {action_guidance}"
    ),
    "latest_result_followup_unavailable": (
        "I still have the latest result in this chat, but I could not safely answer "
        "that follow-up. Please retry in a moment."
    ),
    "private_alpha_save_unavailable": (
        "I cannot move this into Strategies while that surface is off for private "
        "alpha, but the completed run is still part of this chat and can be reopened "
        "from the conversation or Recents."
    ),
    "confirmation_action_guidance": (
        "The visible confirmation is still ready. Use the card to start the "
        "simulation, or use the card controls to change it."
    ),
    "confirmation_action_missing_context": (
        "I do not have an active confirmation to change. Describe the investing idea "
        "again and I will prepare a fresh draft."
    ),
    "confirmation_action_missing_identity": (
        "That confirmation action is missing its card identity. Use the latest card "
        "action before continuing."
    ),
    "confirmation_action_stale_card": (
        "That confirmation was updated. Use the latest visible card and I will keep "
        "the current confirmation intact."
    ),
    "confirmation_state_lost": (
        "I lost the active confirmation state, but your conversation is saved. I can "
        "restate the strategy so you can confirm it again."
    ),
    "confirmation_action_stale_payload": (
        "That confirmation payload is stale. Use the latest visible card and I will "
        "keep the current confirmation intact."
    ),
    "confirmation_cancelled": "No problem. I will leave that draft unrun.",
    "clarification_generation_unavailable": (
        "I could not phrase the follow-up clearly just now. Your draft is still here; "
        "tell me the detail you want to change, or try again in a moment."
    ),
    "result_refine_missing": (
        "I do not have a completed result to refine. Run a strategy first, then use "
        "Refine idea from the result card."
    ),
    "context_macro_recovery": (
        "Macro conditions can be useful context for a historical test. Choose a "
        "symbol, strategy, or comparison window and I can help frame a supported "
        "experiment."
    ),
    "context_corporate_events_recovery": (
        "Corporate events are most useful when tied to a symbol and period. Choose "
        "an equity ticker and I can use events like splits or dividends as context "
        "around a supported historical test."
    ),
    "context_market_movers_recovery": (
        "A market move can be a useful starting point for an experiment. Choose a "
        "symbol or idea and I can turn it into a supported historical test instead "
        "of a live feed."
    ),
    "context_market_movers_seed_recovery": (
        "A short-lived movers snapshot can help pick experiment seeds: {seeds}. "
        "Treat those as symbols to validate, not recommendations or a live ranking. "
        "Choose one and I can shape a supported historical test."
    ),
    "capability_answer_unavailable": (
        "I could not phrase that capability answer clearly just now. Tell me the "
        "asset, period, or supported rule you want to test, or try again in a moment."
    ),
    "runtime_failure": (
        "Something went wrong. Your conversation is saved. Please try again."
    ),
    "artifact_action_invalid_state": (
        "That action is no longer attached to the current conversation state. Use "
        "the latest visible action or tell me what you want to do next."
    ),
    "artifact_action_retry_stale": (
        "That retry belongs to an older failed run. Use the latest retry action or "
        "confirm the setup you want to run."
    ),
    "artifact_action_retry_missing_artifact_id": (
        "That retry is missing its failed-run reference. Use the latest retry action "
        "or confirm the strategy you want me to run."
    ),
    "artifact_action_retry_missing_payload": (
        "I do not have a failed run payload to retry. Use the visible Run backtest "
        "action again, or confirm the strategy you want me to run."
    ),
    "artifact_action_retry_non_retryable": (
        "I still have the failed setup, but rerunning the same payload will hit the "
        "same blocker{blocker_suffix}. Adjust the rule, asset, or date range and I "
        "will keep the idea intact."
    ),
    "artifact_action_retry_rebuilt_confirmation": (
        "I still have that failed setup. I rebuilt the draft so you can review the "
        "card and retry when you are ready."
    ),
    "artifact_action_retry_inactive": (
        "That retry is no longer attached to an active failed run. Use the latest "
        "retry action or confirm the setup you want to run."
    ),
    "execution_data_unavailable": (
        "The setup is still here, but I could not get {data_label} for that run "
        "right now. Try again, change the dates, or choose a different supported "
        "asset."
    ),
}


class RecoveryText(str):
    code: RecoveryMessageCode
    retryable: bool
    params: dict[str, Any]

    def __new__(
        cls,
        value: str,
        *,
        code: RecoveryMessageCode,
        retryable: bool,
        params: dict[str, Any],
    ) -> "RecoveryText":
        instance = str.__new__(cls, value)
        instance.code = code
        instance.retryable = retryable
        instance.params = dict(params)
        return instance


def recovery_message(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    retryable: bool = False,
    **params: Any,
) -> str:
    """Compatibility text for persisted messages.

    Localized UI surfaces must render from the recovery code and params instead.
    The language parameter remains accepted for existing callers, but it does not
    decide prose.
    """

    _ = language
    fallback_params = _fallback_params(code=code, params=params)
    text = RECOVERY_FALLBACK_MESSAGES[code].format(**fallback_params)
    return RecoveryText(
        text,
        code=code,
        retryable=retryable,
        params=params,
    )


def recovery_state(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    retryable: bool,
    **params: Any,
) -> dict[str, Any]:
    _ = language
    state: dict[str, Any] = {
        "code": code,
        "retryable": retryable,
    }
    cleaned_params = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    if cleaned_params:
        state["params"] = cleaned_params
    return state


def recovery_state_stage_patch(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    retryable: bool,
    **params: Any,
) -> dict[str, dict[str, Any]]:
    return {
        "recovery": recovery_state(
            code,
            language=language,
            retryable=retryable,
            **params,
        )
    }


def recovery_state_from_text(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, RecoveryText):
        return None
    return recovery_state(
        value.code,
        retryable=value.retryable,
        **value.params,
    )


def retry_last_turn_stage_patch(message: str) -> dict[str, dict[str, str]] | None:
    cleaned = message.strip()
    if not cleaned:
        return None
    return {"retry_last_turn": {"message": cleaned}}


def _fallback_params(
    *,
    code: RecoveryMessageCode,
    params: dict[str, Any],
) -> dict[str, Any]:
    if code == "artifact_action_retry_non_retryable":
        message = str(params.get("user_safe_message") or "").strip()
        return {
            **params,
            "blocker_suffix": f": {message}" if message else "",
        }
    if code == "execution_data_unavailable":
        data_kind = str(params.get("data_kind") or "").strip()
        data_label = "benchmark data" if data_kind == "benchmark" else "market data"
        return {**params, "data_label": data_label}
    return params

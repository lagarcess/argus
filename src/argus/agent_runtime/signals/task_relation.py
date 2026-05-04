from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from argus.agent_runtime.state.models import ResponseProfileOverrides, TaskSnapshot

BEGINNER_PATTERNS = (
    r"don't know anything about finance",
    r"\bnew to (investing|trading|finance)\b",
    r"\bwhat can you do\b",
    r"\bhelp me understand\b",
)

BACKTEST_PATTERNS = (
    r"\bbacktest\b",
    r"\btest an idea\b",
    r"\brun (it|this|that)\b",
    r"\bsimulate\b",
)

NEW_TASK_PATTERNS = (
    r"\bnow\b",
    r"\binstead\b",
    r"\bnew backtest\b",
    r"\bstart over\b",
)

REFINEMENT_PATTERNS = (
    r"\brefine\b",
    r"\btweak\b",
    r"\badjust\b",
    r"\bchange the\b",
)

CONTINUATION_PATTERNS = (
    r"\bcontinue\b",
    r"\bgo on\b",
    r"\bwhat happened\b",
    r"\bwhy did\b",
)

TONE_OVERRIDE_PATTERNS: dict[str, tuple[str, ...]] = {
    "concise": (
        r"\bbe concise\b",
        r"\bkeep it concise\b",
        r"\bbriefly\b",
        r"\bshort answer\b",
    ),
    "friendly": (
        r"\bbe friendly\b",
        r"\bkeep it friendly\b",
        r"\bin a friendly tone\b",
        r"\bwarm tone\b",
    ),
}

EXPERTISE_OVERRIDE_PATTERNS = (
    r"explain it like i(?:'| a)?m 5",
    r"explain .* simply",
    r"\bin simple terms\b",
)

VERBOSITY_OVERRIDE_PATTERNS = (
    r"\bwalk me through each step\b",
    r"\bstep by step\b",
    r"\bin detail\b",
    r"\bdetailed\b",
)

SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "AAPL": ("apple", "aapl"),
    "TSLA": ("tesla", "tsla"),
    "NVDA": ("nvidia", "nvda"),
    "GOOG": ("google", "goog", "alphabet"),
    "SPY": ("spy", "s&p 500", "s and p 500"),
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth"),
    "SOL": ("solana", "sol"),
}

DATE_RANGE_PATTERNS = (
    r"\blast \d+ (?:day|days|week|weeks|month|months|year|years)\b",
    r"\bover the last \d+ (?:day|days|week|weeks|month|months|year|years)\b",
    r"\b(?:over the )?(?:past|last) (?:day|week|month|year)\b",
    r"\bfrom \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\b",
)


class ExtractedSignals(BaseModel):
    beginner_language_detected: bool = False
    backtest_request_detected: bool = False
    explicit_new_request: bool = False
    explicit_refinement_request: bool = False
    continuation_request_detected: bool = False
    symbols_changed: bool = False
    request_is_under_specified: bool = False
    gray_case_detected: bool = False
    detected_symbols: list[str] = Field(default_factory=list)
    prior_symbols: list[str] = Field(default_factory=list)
    detected_date_range: str | None = None
    response_profile_overrides: ResponseProfileOverrides = Field(
        default_factory=ResponseProfileOverrides
    )
    reason_codes: list[str] = Field(default_factory=list)

    def to_patch_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


def extract_signals(
    *,
    message: str,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
) -> ExtractedSignals:
    lowered = normalize_message(message)
    snapshot = normalize_task_snapshot(latest_task_snapshot)
    reason_codes: list[str] = []

    beginner_language = matches_any(lowered, BEGINNER_PATTERNS)
    if beginner_language:
        reason_codes.append("beginner_language_detected")

    backtest_request = matches_any(lowered, BACKTEST_PATTERNS)
    explicit_new_request = matches_any(lowered, NEW_TASK_PATTERNS)
    explicit_refinement_request = matches_any(lowered, REFINEMENT_PATTERNS)
    continuation_request = matches_any(lowered, CONTINUATION_PATTERNS)

    detected_symbols = detect_symbols(lowered)
    prior_symbols = []
    prior_strategy = None
    if snapshot is not None:
        prior_strategy = (
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
        )
    if prior_strategy is not None and prior_strategy.asset_universe:
        prior_symbols = [
            symbol.upper()
            for symbol in prior_strategy.asset_universe
        ]

    symbols_changed = bool(
        detected_symbols and prior_symbols and detected_symbols != prior_symbols
    )
    if symbols_changed:
        reason_codes.append("symbols_changed")

    detected_date_range = extract_date_range(lowered)

    overrides = resolve_response_profile_overrides(lowered)

    followup_has_pending_strategy = bool(
        snapshot is not None
        and snapshot.pending_strategy_summary is not None
        and (
            explicit_refinement_request
            or "instead" in lowered
            or "weekly" in lowered
            or "monthly" in lowered
            or "keep everything else" in lowered
        )
    )
    if followup_has_pending_strategy:
        explicit_refinement_request = True
        explicit_new_request = False
        symbols_changed = False
        if "strategy_logic_changed" not in reason_codes:
            reason_codes.append("strategy_logic_changed")

    request_is_under_specified = bool(
        (backtest_request or detected_symbols)
        and not followup_has_pending_strategy
        and (
            not detected_symbols
            or detected_date_range is None
            or not explicit_strategy_logic_present(lowered)
        )
    )
    if request_is_under_specified:
        reason_codes.append("request_is_under_specified")

    if explicit_new_request:
        reason_codes.append("explicit_new_request")
    if explicit_refinement_request:
        reason_codes.append("strategy_logic_changed")
    if continuation_request:
        reason_codes.append("conversation_followup_detected")

    gray_case_detected = bool(
        sum(
            1
            for condition in (
                explicit_new_request or symbols_changed,
                explicit_refinement_request,
                continuation_request,
            )
            if condition
        )
        > 1
    )
    if gray_case_detected:
        reason_codes.append("gray_case_detected")

    return ExtractedSignals(
        beginner_language_detected=beginner_language,
        backtest_request_detected=backtest_request,
        explicit_new_request=explicit_new_request,
        explicit_refinement_request=explicit_refinement_request,
        continuation_request_detected=continuation_request,
        symbols_changed=symbols_changed,
        request_is_under_specified=request_is_under_specified,
        gray_case_detected=gray_case_detected,
        detected_symbols=detected_symbols,
        prior_symbols=prior_symbols,
        detected_date_range=detected_date_range,
        response_profile_overrides=overrides,
        reason_codes=reason_codes,
    )


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def normalize_task_snapshot(
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
) -> TaskSnapshot | None:
    if latest_task_snapshot is None:
        return None
    if isinstance(latest_task_snapshot, TaskSnapshot):
        return latest_task_snapshot
    return TaskSnapshot.model_validate(latest_task_snapshot)


def matches_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, message) for pattern in patterns)


def detect_symbols(message: str) -> list[str]:
    detected: list[str] = []
    for symbol, aliases in SYMBOL_ALIASES.items():
        if any(alias_matches(message, alias) for alias in aliases):
            detected.append(symbol)
    return detected


def alias_matches(message: str, alias: str) -> bool:
    escaped = re.escape(alias)
    if re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", message):
        return True
    return False


def extract_date_range(message: str) -> str | None:
    for pattern in DATE_RANGE_PATTERNS:
        match = re.search(pattern, message)
        if match is not None:
            return match.group(0)
    return None


def explicit_strategy_logic_present(message: str) -> bool:
    return " when " in message or " if " in message or " rsi " in f" {message} "


def resolve_response_profile_overrides(message: str) -> ResponseProfileOverrides:
    overrides = ResponseProfileOverrides()
    for tone, patterns in TONE_OVERRIDE_PATTERNS.items():
        if matches_any(message, patterns):
            overrides.tone = tone
            break
    if matches_any(message, EXPERTISE_OVERRIDE_PATTERNS):
        overrides.expertise_mode = "beginner"
    if matches_any(message, VERBOSITY_OVERRIDE_PATTERNS):
        overrides.verbosity = "high"
    return overrides

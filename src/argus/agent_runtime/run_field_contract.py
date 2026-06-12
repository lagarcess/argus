from __future__ import annotations

from datetime import date

from argus.domain.indicators import EXECUTABLE_INDICATORS
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.nlp.natural_time import resolve_current_message_date_patch


def current_message_dca_cadence(message: str) -> str | None:
    """Return a user-stated DCA cadence using the strategy capability contract."""

    tokens = field_fidelity_tokens(str(message or "").casefold())
    if not tokens:
        return None
    capability = STRATEGY_CAPABILITIES.get("dca_accumulation")
    cadence_spec = capability.parameters.get("dca_cadence") if capability else None
    if cadence_spec is None:
        return None
    for cadence in cadence_spec.allowed_values:
        normalized = str(cadence).strip().casefold()
        if not normalized:
            continue
        aliases = [normalized, *cadence_spec.value_aliases.get(normalized, [])]
        for alias in aliases:
            alias_tokens = field_fidelity_tokens(str(alias).casefold())
            if alias_tokens and _contains_ordered_token_span(tokens, alias_tokens):
                return normalized
    return None


def current_message_execution_context_tokens(
    message: str,
    *,
    strategy_type: str | None,
) -> set[str]:
    """Return tokens consumed by strategy capability fields in the current turn."""

    tokens = field_fidelity_tokens(str(message or "").casefold())
    if not tokens:
        return set()
    capability = STRATEGY_CAPABILITIES.get(str(strategy_type or "").strip())
    matched_tokens: set[str] = set()
    if _strategy_type_uses_indicator_context(strategy_type):
        matched_tokens.update(_matched_indicator_context_tokens(tokens))
    if capability is None:
        return matched_tokens

    for parameter in capability.parameters.values():
        alias_phrases: list[str] = []
        for value in parameter.allowed_values:
            normalized = str(value).strip().casefold()
            if not normalized:
                continue
            alias_phrases.append(normalized)
            alias_phrases.extend(
                str(alias).strip().casefold()
                for alias in parameter.value_aliases.get(normalized, [])
                if str(alias).strip()
            )
        for alias in alias_phrases:
            alias_tokens = field_fidelity_tokens(alias)
            if alias_tokens and _contains_ordered_token_span(tokens, alias_tokens):
                matched_tokens.update(alias_tokens)
    return matched_tokens


def _strategy_type_uses_indicator_context(strategy_type: str | None) -> bool:
    return str(strategy_type or "").strip() in {
        "indicator_threshold",
        "rsi_mean_reversion",
        "signal_strategy",
    }


def _matched_indicator_context_tokens(tokens: list[str]) -> set[str]:
    matched_tokens: set[str] = set()
    for spec in EXECUTABLE_INDICATORS.values():
        phrases = [spec.key, spec.label, *spec.aliases]
        for phrase in phrases:
            phrase_tokens = field_fidelity_tokens(str(phrase).casefold())
            if phrase_tokens and _contains_ordered_token_span(tokens, phrase_tokens):
                matched_tokens.update(phrase_tokens)
    return matched_tokens


def _contains_ordered_token_span(tokens: list[str], span: list[str]) -> bool:
    if len(span) > len(tokens):
        return False
    last_start = len(tokens) - len(span)
    for start in range(last_start + 1):
        if tokens[start : start + len(span)] == span:
            return True
    return False


def current_message_date_range(
    message: str,
    *,
    today: date | None = None,
) -> dict[str, str] | None:
    return resolve_current_message_date_patch(message, today=today or date.today())


def field_fidelity_tokens(text: str) -> list[str]:
    separators = ",.;:!?()[]{}"
    cleaned = text
    for separator in separators:
        cleaned = cleaned.replace(separator, " ")
    return [token for token in cleaned.split() if token]


def message_states_bar_timeframe(message: str) -> bool:
    tokens = set(field_fidelity_tokens(str(message or "").casefold()))
    return bool(
        tokens
        & {
            "bar",
            "bars",
            "candle",
            "candles",
            "daily",
            "hour",
            "hourly",
            "intraday",
            "minute",
            "minutes",
            "1d",
            "1h",
            "4h",
        }
    )

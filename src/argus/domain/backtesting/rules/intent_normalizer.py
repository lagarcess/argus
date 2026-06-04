from __future__ import annotations

from dataclasses import dataclass

from .describe import describe_rule_spec
from .models import RuleSpec
from .signals import (
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
)


@dataclass(frozen=True)
class ExplicitSignalRuleIntent:
    rule_spec: RuleSpec
    entry_logic: str
    exit_logic: str
    strategy_thesis: str
    confidence: float = 0.86


@dataclass(frozen=True)
class _IndicatorMention:
    key: str
    period: int
    index: int


_ABOVE_DIRECTION_TOKENS = {
    "above",
    "over",
    "bullish",
    "up",
    "golden",
}
_BELOW_DIRECTION_TOKENS = {
    "below",
    "under",
    "bearish",
    "down",
    "death",
}
_CROSS_TOKENS = {
    "cross",
    "crosses",
    "crossed",
    "crossing",
    "crossover",
    "crossovers",
}
_MOVING_AVERAGE_TOKENS = {
    "ma",
    "sma",
    "ema",
    "average",
    "averages",
}


def explicit_signal_rule_intent_from_text(
    text: str | None,
) -> ExplicitSignalRuleIntent | None:
    tokens = _tokens(text)
    if not tokens:
        return None
    return _moving_average_crossover_intent(tokens) or _macd_crossover_intent(tokens)


def _moving_average_crossover_intent(
    tokens: list[str],
) -> ExplicitSignalRuleIntent | None:
    if not (
        _mentions_moving_average(tokens)
        or _looks_like_plain_moving_average_crossover(tokens)
    ):
        return None
    direction = _crossover_direction(tokens)
    if direction is None:
        direction = "bullish" if _has_cross_token(tokens) else None
    if direction is None:
        return None
    refs = _moving_average_mentions(tokens)
    if len(refs) < 2:
        return None
    fast, slow = sorted(refs[:2], key=lambda item: item.index)
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": fast.key,
        "fast_period": fast.period,
        "slow_indicator": slow.key,
        "slow_period": slow.period,
        "direction": direction,
    }
    try:
        rule_spec = rule_spec_from_moving_average_crossover_rules(
            entry_rule=entry_rule,
            exit_rule=None,
        )
    except ValueError:
        return None
    if rule_spec is None:
        return None
    return _intent_from_rule_spec(
        rule_spec,
        strategy_thesis=(
            f"Test a {_indicator_label(fast.key)} {fast.period}/"
            f"{_indicator_label(slow.key)} {slow.period} crossover."
        ),
    )


def _macd_crossover_intent(tokens: list[str]) -> ExplicitSignalRuleIntent | None:
    if "macd" not in tokens:
        return None
    if "volume" in tokens and "only" not in tokens:
        return None
    direction = _crossover_direction(tokens)
    if direction is None:
        if "bullish" in tokens:
            direction = "bullish"
        elif "bearish" in tokens:
            direction = "bearish"
    if direction is None:
        return None
    rule_spec = rule_spec_from_signal_rule(
        {
            "type": "macd_crossover",
            "direction": direction,
        }
    )
    if rule_spec is None:
        return None
    return _intent_from_rule_spec(
        rule_spec,
        strategy_thesis="Test a MACD signal-line crossover.",
    )


def _intent_from_rule_spec(
    rule_spec: RuleSpec,
    *,
    strategy_thesis: str,
) -> ExplicitSignalRuleIntent | None:
    entry_logic = describe_rule_spec(rule_spec, "entry")
    exit_logic = describe_rule_spec(rule_spec, "exit")
    if not entry_logic or not exit_logic:
        return None
    return ExplicitSignalRuleIntent(
        rule_spec=rule_spec,
        entry_logic=entry_logic,
        exit_logic=exit_logic,
        strategy_thesis=strategy_thesis,
    )


def _tokens(text: str | None) -> list[str]:
    if not text:
        return []
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _mentions_moving_average(tokens: list[str]) -> bool:
    token_set = set(tokens)
    if token_set.intersection({"sma", "ema"}):
        return True
    return "moving" in token_set and bool(
        token_set.intersection({"average", "averages"})
    )


def _looks_like_plain_moving_average_crossover(tokens: list[str]) -> bool:
    if not _has_cross_token(tokens):
        return False
    token_set = set(tokens)
    if token_set.intersection({"rsi", "macd", "bollinger", "volume"}):
        return False
    return len(_positive_periods(tokens)) >= 2


def _crossover_direction(tokens: list[str]) -> str | None:
    token_set = set(tokens)
    if not (
        token_set.intersection(_CROSS_TOKENS)
        or token_set.intersection({"golden", "death", "bullish", "bearish"})
    ):
        return None
    if token_set.intersection(_ABOVE_DIRECTION_TOKENS):
        return "bullish"
    if token_set.intersection(_BELOW_DIRECTION_TOKENS):
        return "bearish"
    return None


def _has_cross_token(tokens: list[str]) -> bool:
    token_set = set(tokens)
    return bool(token_set.intersection(_CROSS_TOKENS))


def _moving_average_mentions(tokens: list[str]) -> list[_IndicatorMention]:
    mentions = _period_anchored_mentions(tokens)
    if len(mentions) >= 2:
        return mentions
    return _compact_crossover_mentions(tokens)


def _period_anchored_mentions(tokens: list[str]) -> list[_IndicatorMention]:
    mentions: list[_IndicatorMention] = []
    for index, token in enumerate(tokens):
        period = _positive_int(token)
        if period is None:
            continue
        window = tokens[index + 1 : index + 7]
        key = _indicator_key_from_window(window)
        if key is None:
            continue
        mentions.append(_IndicatorMention(key=key, period=period, index=index))
    return mentions


def _compact_crossover_mentions(tokens: list[str]) -> list[_IndicatorMention]:
    anchor_index = _first_moving_average_anchor(tokens)
    if anchor_index is None:
        return _plain_crossover_mentions(tokens)
    period_tokens = tokens if anchor_index is None else tokens[: anchor_index + 1]
    periods = _positive_periods(period_tokens)
    if len(periods) < 2:
        return []
    key = "ema" if "ema" in tokens or "exponential" in tokens else "sma"
    return [
        _IndicatorMention(key=key, period=period, index=index)
        for index, period in periods[-2:]
    ]


def _plain_crossover_mentions(tokens: list[str]) -> list[_IndicatorMention]:
    periods = _positive_periods(tokens)
    if len(periods) < 2:
        return []
    key = "ema" if "ema" in tokens or "exponential" in tokens else "sma"
    cross_indexes = [
        index for index, token in enumerate(tokens) if token in _CROSS_TOKENS
    ]
    for cross_index in cross_indexes:
        before = [item for item in periods if item[0] < cross_index]
        after = [item for item in periods if item[0] > cross_index]
        if before and after:
            selected = [before[-1], after[0]]
            return [
                _IndicatorMention(key=key, period=period, index=index)
                for index, period in selected
            ]
        if len(before) >= 2:
            selected = before[-2:]
            return [
                _IndicatorMention(key=key, period=period, index=index)
                for index, period in selected
            ]
    return [
        _IndicatorMention(key=key, period=period, index=index)
        for index, period in periods[:2]
    ]


def _first_moving_average_anchor(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token in _MOVING_AVERAGE_TOKENS:
            return index
    return None


def _positive_periods(tokens: list[str]) -> list[tuple[int, int]]:
    return [
        (index, period)
        for index, token in enumerate(tokens)
        for period in [_positive_int(token)]
        if period is not None
    ]


def _indicator_key_from_window(window: list[str]) -> str | None:
    if "ema" in window or "exponential" in window:
        return "ema"
    if "sma" in window or "simple" in window:
        return "sma"
    if "moving" in window and ("average" in window or "averages" in window):
        return "sma"
    return None


def _indicator_label(key: str) -> str:
    return key.upper()


def _positive_int(value: str) -> int | None:
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None

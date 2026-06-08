from __future__ import annotations

from .describe import describe_condition, describe_rule_spec
from .intent_normalizer import (
    ExplicitSignalRuleIntent,
    explicit_signal_rule_intent_from_text,
)
from .models import Condition, ConditionGroup, RuleSpec, SeriesRef
from .normalization import canonicalize_rule_spec
from .signals import (
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
)
from .validation import required_warmup_bars, validate_rule_spec

__all__ = [
    "Condition",
    "ConditionGroup",
    "ExplicitSignalRuleIntent",
    "RuleSpec",
    "SeriesRef",
    "canonicalize_rule_spec",
    "compile_rule_signals",
    "describe_condition",
    "describe_rule_spec",
    "explicit_signal_rule_intent_from_text",
    "resolve_series",
    "required_warmup_bars",
    "rule_spec_from_moving_average_crossover_rules",
    "rule_spec_from_signal_rule",
    "validate_rule_spec",
]


def compile_rule_signals(*args, **kwargs):
    from .compiler import compile_rule_signals as _compile_rule_signals

    return _compile_rule_signals(*args, **kwargs)


def resolve_series(*args, **kwargs):
    from .series import resolve_series as _resolve_series

    return _resolve_series(*args, **kwargs)

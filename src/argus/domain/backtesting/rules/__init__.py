from __future__ import annotations

from .compiler import compile_rule_signals
from .describe import describe_condition, describe_rule_spec
from .models import Condition, ConditionGroup, RuleSpec, SeriesRef
from .normalization import canonicalize_rule_spec
from .series import resolve_series
from .signals import (
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
)
from .validation import required_warmup_bars, validate_rule_spec

__all__ = [
    "Condition",
    "ConditionGroup",
    "RuleSpec",
    "SeriesRef",
    "canonicalize_rule_spec",
    "compile_rule_signals",
    "describe_condition",
    "describe_rule_spec",
    "resolve_series",
    "required_warmup_bars",
    "rule_spec_from_moving_average_crossover_rules",
    "rule_spec_from_signal_rule",
    "validate_rule_spec",
]

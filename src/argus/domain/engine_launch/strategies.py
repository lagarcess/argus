from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import LaunchBacktestRequest


def normalize_template_name(request: LaunchBacktestRequest) -> str:
    if request.strategy_type == "buy_and_hold":
        return "buy_and_hold"
    if request.strategy_type == "dca_accumulation":
        return "dca_accumulation"
    return "rsi_mean_reversion"


def validate_launch_supported(request: LaunchBacktestRequest) -> None:
    if request.risk_rules:
        raise ValueError("unsupported_risk_rules")

    if request.strategy_type != "indicator_threshold":
        return

    if not request.entry_rule or not request.exit_rule:
        raise ValueError("missing_threshold_rules")

    if not _is_supported_rsi_rule(
        request.entry_rule,
        indicator="rsi",
        operator="below",
        threshold=30.0,
    ):
        raise ValueError("unsupported_indicator_threshold")

    if not _is_supported_rsi_rule(
        request.exit_rule,
        indicator="rsi",
        operator="above",
        threshold=55.0,
    ):
        raise ValueError("unsupported_indicator_threshold")


def _is_supported_rsi_rule(
    rule: dict[str, Any],
    *,
    indicator: str,
    operator: str,
    threshold: float,
) -> bool:
    raw_indicator = str(rule.get("indicator", "")).strip().lower()
    raw_operator = str(rule.get("operator", "")).strip().lower()
    raw_threshold = rule.get("threshold")

    try:
        normalized_threshold = float(raw_threshold)
    except (TypeError, ValueError):
        return False

    return (
        raw_indicator == indicator
        and raw_operator == operator
        and normalized_threshold == threshold
    )

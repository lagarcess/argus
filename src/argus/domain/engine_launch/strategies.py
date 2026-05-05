from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.indicators import normalize_indicator_parameters


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

    if _indicator_threshold_parameters(request) is None:
        raise ValueError("unsupported_indicator_threshold")


def indicator_threshold_parameters(request: LaunchBacktestRequest) -> dict[str, Any]:
    parameters = _indicator_threshold_parameters(request)
    if parameters is None:
        raise ValueError("unsupported_indicator_threshold")
    return parameters


def _indicator_threshold_parameters(
    request: LaunchBacktestRequest,
) -> dict[str, Any] | None:
    if not request.entry_rule or not request.exit_rule:
        return None

    entry_indicator = str(request.entry_rule.get("indicator") or "rsi")
    exit_indicator = str(request.exit_rule.get("indicator") or entry_indicator)
    entry_operator = str(request.entry_rule.get("operator") or "").strip().lower()
    exit_operator = str(request.exit_rule.get("operator") or "").strip().lower()
    if entry_operator != "below" or exit_operator != "above":
        return None
    if entry_indicator.strip().lower() != exit_indicator.strip().lower():
        return None

    try:
        return normalize_indicator_parameters(
            entry_indicator,
            {
                **request.parameters,
                "entry_threshold": request.entry_rule.get("threshold"),
                "exit_threshold": request.exit_rule.get("threshold"),
            },
        )
    except ValueError:
        return None

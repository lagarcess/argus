from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES
from argus.domain.capability_status import CapabilityStatus

AssetClass = Literal["equity", "crypto", "currency_pair"]
SlotPolicy = Literal["required", "defaultable", "clarify_if_missing"]
ExecutionStrategyType = Literal[
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
]


class ParameterSpec(BaseModel):
    key: str
    policy: SlotPolicy
    default: Any = None
    allowed_values: list[Any] = Field(default_factory=list)
    description: str
    value_aliases: dict[str, list[str]] = Field(default_factory=dict)


class ResultChartExplorationSpec(BaseModel):
    # Generic, display-free result-chart exploration semantics. The resolver turns
    # these into plain chart hints; the frontend never sees strategy or parameter
    # identity.
    minimum_visible_observations: int = Field(default=6, ge=1)
    minimum_meaningful_duration: str | None = None
    cycle_parameter: str | None = None
    cycle_duration_by_value: dict[str, str] = Field(default_factory=dict)
    minimum_visible_cycles: int = Field(default=2, ge=1)


class StrategyCapability(BaseModel):
    template: str
    display_name: str
    aliases: list[str]
    execution_strategy_type: ExecutionStrategyType | None = None
    supported_asset_classes: list[AssetClass]
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    # Typed capability status (single source of truth for derived allow-lists). A
    # template is only `executable` when it is reachable end-to-end via a supported
    # user-facing path; drafts compute a signal but have no supported path.
    status: CapabilityStatus = "executable"
    # True when the strategy runs with a fixed, non-user-tunable parameterization
    # (e.g. buy_the_dip's hardcoded -3% trigger), so copy never implies tunability.
    fixed_parameters: bool = False
    result_chart_exploration: ResultChartExplorationSpec = Field(
        default_factory=ResultChartExplorationSpec
    )

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> "StrategyCapability":
        # Draft-ness is encoded once: an executable template has an execution type, a
        # draft/future one does not. Making the contradictory pair unrepresentable stops
        # the derived allow-lists (EXECUTABLE_TEMPLATES vs SUPPORTED_STRATEGY_TYPES) from
        # silently disagreeing.
        if self.status == "executable" and self.execution_strategy_type is None:
            raise ValueError(
                f"executable capability {self.template!r} requires an "
                "execution_strategy_type"
            )
        if self.status != "executable" and self.execution_strategy_type is not None:
            raise ValueError(
                f"non-executable capability {self.template!r} must not set an "
                "execution_strategy_type"
            )
        return self


STRATEGY_CAPABILITIES: dict[str, StrategyCapability] = {
    "buy_and_hold": StrategyCapability(
        template="buy_and_hold",
        display_name="Buy and Hold",
        aliases=[
            "lump_sum",
            "lump_sum_investment",
            "one_time_investment",
        ],
        execution_strategy_type="buy_and_hold",
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        result_chart_exploration=ResultChartExplorationSpec(
            minimum_meaningful_duration="P1M"
        ),
    ),
    "buy_the_dip": StrategyCapability(
        template="buy_the_dip",
        display_name="Buy the Dip",
        aliases=[
            "buy_dips",
            "dip_buying",
        ],
        execution_strategy_type="indicator_threshold",
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        # Hardcoded -3% trigger with no user-tunable parameters (see signals.py).
        fixed_parameters=True,
    ),
    "rsi_mean_reversion": StrategyCapability(
        template="rsi_mean_reversion",
        display_name="RSI Threshold",
        aliases=[
            "rsi",
            "rsi_threshold",
            "oversold",
            "mean_reversion",
            "indicator",
            "indicator_threshold",
            "threshold",
            "rule_based",
        ],
        execution_strategy_type="indicator_threshold",
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        parameters={
            "indicator": ParameterSpec(
                key="indicator",
                policy="defaultable",
                default="rsi",
                allowed_values=["rsi"],
                description="Executable indicator for this threshold strategy.",
                value_aliases={},
            ),
            "indicator_period": ParameterSpec(
                key="indicator_period",
                policy="defaultable",
                default=14,
                description="Number of bars used to calculate the indicator.",
            ),
            "entry_threshold": ParameterSpec(
                key="entry_threshold",
                policy="defaultable",
                default=30,
                description="Indicator value that triggers an entry.",
            ),
            "exit_threshold": ParameterSpec(
                key="exit_threshold",
                policy="defaultable",
                default=55,
                description="Indicator value that triggers an exit.",
            ),
        },
    ),
    "moving_average_crossover": StrategyCapability(
        template="moving_average_crossover",
        display_name="Moving Average Crossover",
        aliases=[
            "ma_crossover",
            "signal",
            "signal_strategy",
            "golden_cross",
            "death_cross",
        ],
        execution_strategy_type="signal_strategy",
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
    "dca_accumulation": StrategyCapability(
        template="dca_accumulation",
        display_name="DCA Accumulation",
        aliases=[
            "dca",
            "accumulation",
            "dollar_cost_averaging",
            "recurring_accumulation",
            "recurring_buy",
            "recurring_buys",
        ],
        execution_strategy_type="dca_accumulation",
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        result_chart_exploration=ResultChartExplorationSpec(
            cycle_parameter="dca_cadence",
            cycle_duration_by_value={
                "daily": "P1D",
                "weekly": "P1W",
                "biweekly": "P2W",
                "monthly": "P1M",
                "quarterly": "P3M",
            },
            minimum_visible_cycles=2,
        ),
        parameters={
            "dca_cadence": ParameterSpec(
                key="dca_cadence",
                policy="clarify_if_missing",
                default="monthly",
                allowed_values=list(SUPPORTED_DCA_CADENCE_VALUES),
                description="How often Argus makes a fixed-dollar purchase.",
                value_aliases={},
            )
        },
    ),
    # Draft templates: no execution_strategy_type and no supported user-facing path.
    # Kept in the registry as the single source of capability truth (status=draft) so
    # every derived allow-list excludes them by construction.
    "momentum_breakout": StrategyCapability(
        template="momentum_breakout",
        display_name="Momentum Breakout",
        aliases=["momentum", "breakout"],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        status="draft",
    ),
    "trend_follow": StrategyCapability(
        template="trend_follow",
        display_name="Trend Follow",
        aliases=[
            "trend_following",
            "trend",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        status="draft",
    ),
}


def _scaled_calendar_duration(duration: str, cycles: int) -> str | None:
    # Only single-unit ISO-8601 calendar durations (P<number><D|W|M|Y>) are typed
    # capability inputs; anything else degrades to the observation-only policy.
    if not duration.startswith("P") or len(duration) < 3:
        return None
    unit = duration[-1]
    if unit not in {"D", "W", "M", "Y"}:
        return None
    try:
        amount = int(duration[1:-1])
    except ValueError:
        return None
    if amount < 1 or cycles < 1:
        return None
    return f"P{amount * cycles}{unit}"


def resolve_result_chart_exploration_policy(
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a capability's exploration spec to generic chart hints.

    The returned mapping carries only display-free presentation hints
    (`minimum_visible_observations`, optional `minimum_meaningful_duration`);
    strategy identity, cadence parameter keys, and cycle math stay backend-only.
    """
    template = str(config.get("template") or "").strip()
    capability = STRATEGY_CAPABILITIES.get(template)
    spec = (
        capability.result_chart_exploration
        if capability is not None
        else ResultChartExplorationSpec()
    )
    duration = spec.minimum_meaningful_duration
    if spec.cycle_parameter:
        parameters = config.get("parameters")
        parameter_values = parameters if isinstance(parameters, Mapping) else {}
        cycle_value = str(parameter_values.get(spec.cycle_parameter) or "").strip()
        one_cycle = spec.cycle_duration_by_value.get(cycle_value)
        resolved = (
            _scaled_calendar_duration(one_cycle, spec.minimum_visible_cycles)
            if one_cycle
            else None
        )
        if resolved is not None:
            duration = resolved

    policy: dict[str, Any] = {
        "minimum_visible_observations": spec.minimum_visible_observations
    }
    if duration:
        policy["minimum_meaningful_duration"] = duration
    return policy

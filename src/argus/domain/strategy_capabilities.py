from typing import Any, Literal

from pydantic import BaseModel, Field

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

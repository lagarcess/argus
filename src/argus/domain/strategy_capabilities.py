from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES

AssetClass = Literal["equity", "crypto", "currency_pair"]
SlotPolicy = Literal["required", "defaultable", "clarify_if_missing"]


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
    supported_asset_classes: list[AssetClass]
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)


STRATEGY_CAPABILITIES: dict[str, StrategyCapability] = {
    "buy_and_hold": StrategyCapability(
        template="buy_and_hold",
        display_name="Buy and Hold",
        aliases=[
            "buy and hold",
            "comprar y mantener",
            "mantener",
            "hold",
            "compra y mantener",
            "lump sum",
            "lump_sum",
            "lump sum investment",
            "lump_sum_investment",
            "one time investment",
            "one_time_investment",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
    "buy_the_dip": StrategyCapability(
        template="buy_the_dip",
        display_name="Buy the Dip",
        aliases=[
            "buy the dip",
            "buy dips",
            "dip buying",
            "compra en caidas",
            "compra en bajadas",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
    "rsi_mean_reversion": StrategyCapability(
        template="rsi_mean_reversion",
        display_name="RSI Threshold",
        aliases=[
            "rsi",
            "oversold",
            "mean reversion",
            "reversion a la media",
            "sobreventa",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        parameters={
            "indicator": ParameterSpec(
                key="indicator",
                policy="defaultable",
                default="rsi",
                allowed_values=["rsi"],
                description="Executable indicator for this threshold strategy.",
                value_aliases={"rsi": ["rsi", "indice de fuerza relativa"]},
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
            "moving average",
            "ma crossover",
            "golden cross",
            "death cross",
            "cruce de medias",
            "cruce de medias moviles",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
    "dca_accumulation": StrategyCapability(
        template="dca_accumulation",
        display_name="DCA Accumulation",
        aliases=[
            "dca",
            "dollar cost averaging",
            "accumulation",
            "promedio de costo",
            "acumulacion",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
        parameters={
            "dca_cadence": ParameterSpec(
                key="dca_cadence",
                policy="clarify_if_missing",
                default="monthly",
                allowed_values=list(SUPPORTED_DCA_CADENCE_VALUES),
                description="How often Argus makes a fixed-dollar purchase.",
                value_aliases={
                    "daily": [
                        "every day",
                        "each day",
                        "per day",
                        "diario",
                        "cada dia",
                        "diariamente",
                    ],
                    "weekly": [
                        "every week",
                        "each week",
                        "per week",
                        "semanal",
                        "cada semana",
                        "semanalmente",
                    ],
                    "biweekly": [
                        "biweekly",
                        "every two weeks",
                        "every other week",
                        "quincenal",
                        "cada dos semanas",
                    ],
                    "monthly": [
                        "every month",
                        "each month",
                        "per month",
                        "mensual",
                        "cada mes",
                        "mensualmente",
                    ],
                    "quarterly": [
                        "quarterly",
                        "every quarter",
                        "each quarter",
                        "per quarter",
                        "trimestral",
                        "cada trimestre",
                    ],
                },
            )
        },
    ),
    "momentum_breakout": StrategyCapability(
        template="momentum_breakout",
        display_name="Momentum Breakout",
        aliases=["momentum", "breakout", "ruptura de momentum", "rompimiento"],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
    "trend_follow": StrategyCapability(
        template="trend_follow",
        display_name="Trend Follow",
        aliases=[
            "trend follow",
            "trend following",
            "trend",
            "seguimiento de tendencia",
            "tendencia",
        ],
        supported_asset_classes=["equity", "crypto", "currency_pair"],
    ),
}

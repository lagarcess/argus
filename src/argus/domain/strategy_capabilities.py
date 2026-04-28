from typing import Any, Literal

from pydantic import BaseModel, Field

AssetClass = Literal["equity", "crypto"]
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
        aliases=["buy and hold", "comprar y mantener", "mantener", "hold", "compra y mantener"],
        supported_asset_classes=["equity", "crypto"],
    ),
    "buy_the_dip": StrategyCapability(
        template="buy_the_dip",
        display_name="Buy the Dip",
        aliases=["buy the dip", "buy dips", "dip buying", "compra en caidas", "compra en bajadas"],
        supported_asset_classes=["equity", "crypto"],
    ),
    "rsi_mean_reversion": StrategyCapability(
        template="rsi_mean_reversion",
        display_name="RSI Mean Reversion",
        aliases=["rsi", "oversold", "mean reversion", "reversion a la media", "sobreventa"],
        supported_asset_classes=["equity", "crypto"],
    ),
    "moving_average_crossover": StrategyCapability(
        template="moving_average_crossover",
        display_name="Moving Average Crossover",
        aliases=["moving average", "ma crossover", "golden cross", "death cross", "cruce de medias", "cruce de medias moviles"],
        supported_asset_classes=["equity", "crypto"],
    ),
    "dca_accumulation": StrategyCapability(
        template="dca_accumulation",
        display_name="DCA Accumulation",
        aliases=["dca", "dollar cost averaging", "accumulation", "promedio de costo", "acumulacion"],
        supported_asset_classes=["equity", "crypto"],
        parameters={
            "dca_cadence": ParameterSpec(
                key="dca_cadence",
                policy="clarify_if_missing",
                default="monthly",
                allowed_values=["daily", "weekly", "monthly"],
                description="How often Argus makes a fixed-dollar purchase.",
                value_aliases={
                    "daily": ["diario", "cada dia", "diariamente"],
                    "weekly": ["semanal", "cada semana", "semanalmente"],
                    "monthly": ["mensual", "cada mes", "mensualmente"],
                },
            )

        },
    ),
    "momentum_breakout": StrategyCapability(
        template="momentum_breakout",
        display_name="Momentum Breakout",
        aliases=["momentum", "breakout", "ruptura de momentum", "rompimiento"],
        supported_asset_classes=["equity", "crypto"],
    ),
    "trend_follow": StrategyCapability(
        template="trend_follow",
        display_name="Trend Follow",
        aliases=["trend follow", "trend following", "trend", "seguimiento de tendencia", "tendencia"],
        supported_asset_classes=["equity", "crypto"],
    ),
}

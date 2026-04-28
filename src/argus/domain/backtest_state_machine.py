from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

BacktestTurnAction = Literal[
    "ask_missing",
    "await_confirmation",
    "run_backtest",
    "edit_backtest",
    "cancel_backtest",
    "answer",
    "cancel",
]
ConfirmationAction = Literal[
    "accept_and_run",
    "edit_parameters",
    "cancel_backtest",
    "none",
]


class BacktestParamsUpdate(BaseModel):
    template: str | None = None
    symbols: list[str] | None = None
    asset_class: Literal["equity", "crypto"] | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    starting_capital: float | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    def has_updates(self) -> bool:
        data = self.model_dump(exclude_none=True)
        params = data.pop("parameters", None)
        return bool(data or params)


class BacktestParams(BaseModel):
    template: str | None = None
    symbols: list[str] | None = None
    asset_class: Literal["equity", "crypto"] | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    starting_capital: float | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class BacktestConversationState(BaseModel):
    params: BacktestParams = Field(default_factory=BacktestParams)
    missing_fields: list[str] = Field(default_factory=list)
    awaiting_confirmation: bool = False
    confirmed_at: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class BacktestTurnResult:
    action: BacktestTurnAction
    state: BacktestConversationState
    message: str
    config: dict[str, Any] | None = None


def merge_params(
    current: BacktestParams,
    update: BacktestParamsUpdate,
) -> BacktestParams:
    data = current.model_dump()
    update_data = update.model_dump(exclude_none=True)
    update_params = update_data.pop("parameters", None)
    data.update(update_data)
    if update_params:
        data["parameters"] = {**data.get("parameters", {}), **update_params}
    return BacktestParams.model_validate(data)


def missing_required_fields(params: BacktestParams) -> list[str]:
    missing: list[str] = []
    if not params.template:
        missing.append("template")
    if not params.symbols:
        missing.append("symbols")
    if not missing and params.template:
        capability = STRATEGY_CAPABILITIES.get(params.template)
        if capability:
            for key, spec in capability.parameters.items():
                if spec.policy == "clarify_if_missing" and params.parameters.get(key) is None:
                    missing.append(key)
    return missing


def is_explicit_confirmation(message: str) -> bool:
    return message.strip().lower() in {
        "yes",
        "y",
        "yeah",
        "yep",
        "confirm",
        "confirmed",
        "run it",
        "go ahead",
        "si",
        "sí",
        "dale",
        "confirmo",
    }


def infer_asset_class(symbols: list[str] | None) -> Literal["equity", "crypto"]:
    crypto_symbols = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT"}
    for symbol in symbols or []:
        up = str(symbol).upper()
        if up in crypto_symbols or "/" in up or up.endswith("USD"):
            return "crypto"
    return "equity"


def build_backtest_config(params: BacktestParams) -> dict[str, Any]:
    asset_class = params.asset_class or infer_asset_class(params.symbols)
    end_date = params.end_date or date.today().isoformat()
    start_date = params.start_date or (date.today() - timedelta(days=365)).isoformat()
    return {
        "template": params.template,
        "asset_class": asset_class,
        "symbols": params.symbols or [],
        "timeframe": params.timeframe or "1D",
        "start_date": start_date,
        "end_date": end_date,
        "side": "long",
        "starting_capital": params.starting_capital or 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "BTC" if asset_class == "crypto" else "SPY",
        "parameters": dict(params.parameters),
    }


def confirmation_summary(params: BacktestParams, language: str) -> str:
    config = build_backtest_config(params)
    template_name = str(config["template"]).replace("_", " ")
    symbols = ", ".join(config["symbols"])
    if language.lower().startswith("es"):
        return (
            "Antes de correr el backtest, confirma estos datos:\n\n"
            f"- Estrategia: {template_name}\n"
            f"- Símbolos: {symbols}\n"
            f"- Periodo: {config['start_date']} a {config['end_date']}\n"
            f"- Capital inicial: ${config['starting_capital']:,.0f}\n"
            f"- Supuestos: long-only, peso igual, sin comisiones ni deslizamiento, "
            f"benchmark {config['benchmark_symbol']}.\n\n"
            "Responde sí para ejecutarlo, o dime qué cambiar."
        )
    return (
        "Before I run the backtest, confirm these details:\n\n"
        f"- Strategy: {template_name}\n"
        f"- Symbols: {symbols}\n"
        f"- Period: {config['start_date']} to {config['end_date']}\n"
        f"- Starting capital: ${config['starting_capital']:,.0f}\n"
        f"- Assumptions: long-only, equal weight, no fees or slippage, "
        f"benchmark {config['benchmark_symbol']}.\n\n"
        "Choose one:\n"
        "1. Run this\n"
        "2. Change something\n"
        "3. Cancel"
    )


def missing_field_message(missing: list[str], params: BacktestParams, language: str) -> str:
    is_es = language.lower().startswith("es")
    first = missing[0]
    if first == "template":
        return (
            "¿Qué estrategia quieres probar?"
            if is_es
            else "What strategy do you want to test?"
        )
    if first == "symbols":
        template = params.template.replace("_", " ") if params.template else "that strategy"
        return (
            f"¿Con qué símbolos quieres correr {template}?"
            if is_es
            else f"Which symbols should I use for {template}?"
        )
    if first == "dca_cadence":
        return (
            "¿Cada cuánto quieres que Argus compre: diario, semanal o mensual?"
            if is_es
            else "How often should Argus buy: daily, weekly, or monthly?"
        )
    return (
        f"Necesito este dato antes de seguir: {first}."
        if is_es
        else f"I need this before we continue: {first}."
    )


def apply_backtest_turn(
    *,
    state: BacktestConversationState,
    update: BacktestParamsUpdate,
    message: str,
    language: str,
    confirmation_action: ConfirmationAction = "none",
) -> BacktestTurnResult:
    is_es = language.lower().startswith("es")
    has_pending_params = bool(
        state.params.template
        or state.params.symbols
        or state.params.asset_class
        or state.params.timeframe
        or state.params.start_date
        or state.params.end_date
        or state.params.starting_capital
        or state.params.parameters
    )
    if (
        (state.awaiting_confirmation or has_pending_params)
        and not update.has_updates()
        and confirmation_action == "cancel_backtest"
    ):
        return BacktestTurnResult(
            action="cancel_backtest",
            state=BacktestConversationState(),
            message=(
                "Listo, cancele ese backtest. Podemos explorar otra idea cuando quieras."
                if is_es
                else "Cancelled. We can explore a different idea whenever you're ready."
            ),
        )

    if (
        state.awaiting_confirmation
        and not update.has_updates()
        and confirmation_action == "edit_parameters"
    ):
        return BacktestTurnResult(
            action="edit_backtest",
            state=state.model_copy(update={"awaiting_confirmation": False}),
            message=(
                "Claro. Que quieres cambiar: estrategia, simbolos, periodo o capital?"
                if is_es
                else "What would you like to change? Strategy, symbols, period, or starting capital?"
            ),
        )

    params = merge_params(state.params, update) if update.has_updates() else state.params
    missing = missing_required_fields(params)
    base_state = BacktestConversationState(
        params=params,
        missing_fields=missing,
        awaiting_confirmation=False,
        confirmed_at=None,
    )

    if missing:
        return BacktestTurnResult(
            action="ask_missing",
            state=base_state,
            message=missing_field_message(missing, params, language),
        )

    summary = confirmation_summary(params, language)
    awaiting_state = base_state.model_copy(
        update={"awaiting_confirmation": True, "summary": summary}
    )

    confirmed = confirmation_action == "accept_and_run" or is_explicit_confirmation(message)
    if state.awaiting_confirmation and not update.has_updates() and confirmed:
        return BacktestTurnResult(
            action="run_backtest",
            state=awaiting_state.model_copy(
                update={
                    "awaiting_confirmation": False,
                    "confirmed_at": date.today().isoformat(),
                }
            ),
            message="",
            config=build_backtest_config(params),
        )

    return BacktestTurnResult(
        action="await_confirmation",
        state=awaiting_state,
        message=summary,
    )

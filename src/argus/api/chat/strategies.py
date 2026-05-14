from __future__ import annotations

from argus.api import state as api_state
from argus.api.schemas import BacktestRun, Strategy, User
from argus.domain.store import utcnow


def strategy_template_from_run(run: BacktestRun) -> str:
    template = str(run.config_snapshot.get("template") or "buy_and_hold")
    supported_templates = {
        "buy_and_hold",
        "buy_the_dip",
        "rsi_mean_reversion",
        "moving_average_crossover",
        "dca_accumulation",
        "momentum_breakout",
        "trend_follow",
    }
    return template if template in supported_templates else "buy_and_hold"


def save_strategy_from_run(*, user: User, run: BacktestRun) -> Strategy:
    if run.strategy_id:
        existing = (
            api_state.supabase_gateway.get_strategy(
                user_id=user.id, strategy_id=run.strategy_id
            )
            if api_state.supabase_gateway is not None
            else api_state.store.strategies.get(run.strategy_id)
        )
        if existing is not None:
            _mark_run_saved(run=run, strategy_id=existing.id)
            return existing

    now = utcnow()
    template = strategy_template_from_run(run)
    strategy_name = (
        run.conversation_result_card.get("title") or f"{', '.join(run.symbols)} idea"
    )
    parameters = dict(run.config_snapshot)
    payload = {
        "name": strategy_name,
        "name_source": "ai_generated",
        "template": template,
        "asset_class": run.asset_class,
        "symbols": run.symbols,
        "parameters": parameters,
        "metrics_preferences": [
            "total_return_pct",
            "max_drawdown_pct",
            "benchmark_delta",
        ],
        "benchmark_symbol": run.benchmark_symbol,
        "conversation_id": run.conversation_id,
    }
    if api_state.supabase_gateway is not None:
        strategy = api_state.supabase_gateway.create_strategy(
            user_id=user.id, payload=payload
        )
    else:
        strategy = Strategy(
            id=api_state.store.new_id(),
            name=strategy_name,
            name_source="ai_generated",
            template=template,  # type: ignore[arg-type]
            asset_class=run.asset_class,
            symbols=run.symbols,
            parameters=parameters,
            metrics_preferences=payload["metrics_preferences"],
            benchmark_symbol=run.benchmark_symbol,
            created_at=now,
            updated_at=now,
        )
        api_state.store.strategies[strategy.id] = strategy
    run.strategy_id = strategy.id
    _mark_run_saved(run=run, strategy_id=strategy.id)
    return strategy


def _mark_run_saved(*, run: BacktestRun, strategy_id: str) -> None:
    run.strategy_id = strategy_id
    card = dict(run.conversation_result_card)
    card["saved_strategy_id"] = strategy_id
    card["saved_state"] = {"status": "saved", "strategy_id": strategy_id}
    actions = card.get("actions")
    if isinstance(actions, list):
        card["actions"] = [
            action
            for action in actions
            if not (
                isinstance(action, dict)
                and action.get("type") == "save_strategy"
            )
        ]
    run.conversation_result_card = card

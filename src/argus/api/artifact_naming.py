from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.message_store import load_runtime_thread_history
from argus.api.naming import suggest_entity_name
from argus.api.schemas import BacktestRun, Conversation, Strategy
from argus.domain.store import utcnow

MAX_ARTIFACT_NAME_CHARS = 80


def maybe_generate_conversation_title(
    *,
    user_id: str,
    conversation_id: str,
    language: str | None,
    current_run: BacktestRun | None = None,
    user_message: str | None = None,
    assistant_message: str | None = None,
) -> str | None:
    """Generate a conversation title as durable polish, never runtime truth."""

    conversation = _get_conversation(user_id=user_id, conversation_id=conversation_id)
    if conversation is None or conversation.title_source != "system_default":
        return None

    run = (
        current_run
        if current_run is not None and current_run.status == "completed"
        else _latest_completed_run_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )
    )
    context = (
        _conversation_title_context_from_run(run)
        if run is not None
        else _conversation_title_context_from_messages(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
    )
    if not context.strip():
        return None

    candidate = _clean_name(
        suggest_entity_name(
            entity_type="conversation",
            context=context,
            language=language or conversation.language,
        )
    )
    if candidate is None:
        return None

    refreshed = _get_conversation(user_id=user_id, conversation_id=conversation_id)
    if refreshed is None or refreshed.title_source != "system_default":
        return None

    _patch_conversation_title(
        user_id=user_id,
        conversation_id=conversation_id,
        title=candidate,
    )
    return candidate


def maybe_generate_saved_strategy_name(
    *,
    user_id: str,
    strategy_id: str,
    run: BacktestRun,
    language: str | None,
) -> str | None:
    """Upgrade fallback saved strategy names without touching run evidence."""

    strategy = _get_strategy(user_id=user_id, strategy_id=strategy_id)
    if strategy is None or strategy.name_source == "user_renamed":
        return None

    context = _strategy_name_context_from_run(run)
    if not context.strip():
        return None

    candidate = _clean_name(
        suggest_entity_name(
            entity_type="strategy",
            context=context,
            language=language,
        )
    )
    if candidate is None:
        return None

    refreshed = _get_strategy(user_id=user_id, strategy_id=strategy_id)
    if refreshed is None or refreshed.name_source == "user_renamed":
        return None

    _patch_strategy_name(
        user_id=user_id,
        strategy_id=strategy_id,
        name=candidate,
    )
    return candidate


def _get_conversation(*, user_id: str, conversation_id: str) -> Conversation | None:
    if api_state.supabase_gateway is not None:
        try:
            return api_state.supabase_gateway.get_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
            )
        except Exception:
            logger.opt(exception=True).warning(
                "Conversation read failed during artifact naming",
                user_id=user_id,
                conversation_id=conversation_id,
            )
    return api_state.store.conversations.get(conversation_id)


def _get_strategy(*, user_id: str, strategy_id: str) -> Strategy | None:
    if api_state.supabase_gateway is not None:
        try:
            return api_state.supabase_gateway.get_strategy(
                user_id=user_id,
                strategy_id=strategy_id,
            )
        except Exception:
            logger.opt(exception=True).warning(
                "Strategy read failed during artifact naming",
                user_id=user_id,
                strategy_id=strategy_id,
            )
    return api_state.store.strategies.get(strategy_id)


def _latest_completed_run_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
) -> BacktestRun | None:
    if api_state.supabase_gateway is not None:
        try:
            return api_state.supabase_gateway.get_latest_completed_run_for_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
            )
        except AttributeError:
            logger.warning(
                "Supabase gateway has no latest run lookup for artifact naming",
                conversation_id=conversation_id,
            )
        except Exception:
            logger.opt(exception=True).warning(
                "Latest completed run read failed during artifact naming",
                user_id=user_id,
                conversation_id=conversation_id,
            )

    runs = [
        run
        for run in api_state.store.backtest_runs.values()
        if isinstance(run, BacktestRun)
        and run.conversation_id == conversation_id
        and run.status == "completed"
        and api_state.store.backtest_run_owners.get(run.id) in {None, user_id}
    ]
    if not runs:
        return None
    return max(runs, key=lambda run: run.created_at)


def _patch_conversation_title(
    *,
    user_id: str,
    conversation_id: str,
    title: str,
) -> None:
    patch = {"title": title, "title_source": "ai_generated"}
    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.patch_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                patch=dict(patch),
            )
            return
        except Exception:
            logger.opt(exception=True).warning(
                "Conversation title patch failed during artifact naming",
                user_id=user_id,
                conversation_id=conversation_id,
            )

    conversation = api_state.store.conversations.get(conversation_id)
    if conversation is not None:
        api_state.store.conversations[conversation_id] = conversation.model_copy(
            update={**patch, "updated_at": utcnow()}
        )


def _patch_strategy_name(
    *,
    user_id: str,
    strategy_id: str,
    name: str,
) -> None:
    patch = {"name": name, "name_source": "ai_generated"}
    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.patch_strategy(
                user_id=user_id,
                strategy_id=strategy_id,
                patch=dict(patch),
            )
            return
        except Exception:
            logger.opt(exception=True).warning(
                "Strategy name patch failed during artifact naming",
                user_id=user_id,
                strategy_id=strategy_id,
            )

    strategy = api_state.store.strategies.get(strategy_id)
    if strategy is not None:
        api_state.store.strategies[strategy_id] = strategy.model_copy(
            update={**patch, "updated_at": utcnow()}
        )


def _conversation_title_context_from_run(run: BacktestRun) -> str:
    return "\n".join(
        [
            "Name this Argus conversation from the most relevant completed run.",
            _run_fact_context(run),
            "Prefer the user's tested idea over generic result labels.",
        ]
    )


def _strategy_name_context_from_run(run: BacktestRun) -> str:
    return "\n".join(
        [
            "Name this saved Argus strategy from canonical run facts.",
            _run_fact_context(run),
            "Use a reusable strategy-style name, not a sentence.",
        ]
    )


def _conversation_title_context_from_messages(
    *,
    user_id: str,
    conversation_id: str,
    user_message: str | None,
    assistant_message: str | None,
) -> str:
    lines = ["Name this Argus conversation from the meaningful chat context."]
    recent = load_runtime_thread_history(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=8,
    )
    for message in recent:
        content = _clip(str(message.content), 360)
        if content:
            lines.append(f"{message.role}: {content}")
    if user_message:
        lines.append(f"latest_user: {_clip(user_message, 360)}")
    if assistant_message:
        lines.append(f"latest_assistant: {_clip(assistant_message, 360)}")
    lines.append("Avoid generic titles like New idea.")
    return "\n".join(lines)


def _run_fact_context(run: BacktestRun) -> str:
    config = run.config_snapshot
    resolved = config.get("resolved_strategy")
    if not isinstance(resolved, dict):
        resolved = {}
    date_range = _value_from_dicts("date_range", resolved, config)
    lines = [
        f"symbols: {', '.join(run.symbols)}",
        f"asset_class: {run.asset_class}",
        f"benchmark: {run.benchmark_symbol}",
        f"template: {config.get('template') or resolved.get('strategy_type')}",
        f"date_range: {_format_value(date_range)}",
    ]
    thesis = resolved.get("strategy_thesis") or config.get("strategy_thesis")
    if thesis:
        lines.append(f"thesis: {_clip(str(thesis), 360)}")

    title = run.conversation_result_card.get("title")
    if title:
        lines.append(f"result_card_title: {_clip(str(title), 160)}")

    performance = _aggregate_performance(run.metrics)
    for key in (
        "total_return_pct",
        "benchmark_return_pct",
        "delta_vs_benchmark_pct",
        "max_drawdown_pct",
        "win_rate",
    ):
        value = performance.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def _aggregate_performance(metrics: dict[str, Any]) -> dict[str, Any]:
    aggregate = metrics.get("aggregate")
    if not isinstance(aggregate, dict):
        return {}
    performance = aggregate.get("performance")
    return performance if isinstance(performance, dict) else {}


def _value_from_dicts(key: str, *dicts: dict[str, Any]) -> Any:
    for item in dicts:
        value = item.get(key)
        if value is not None:
            return value
    return None


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None:
        return "unknown"
    return str(value)


def _clip(value: str, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 1].rstrip()}..."


def _clean_name(candidate: str | None) -> str | None:
    if candidate is None:
        return None
    name = " ".join(candidate.split()).strip()
    while len(name) >= 2 and name[0] in {"'", '"'} and name[-1] == name[0]:
        name = name[1:-1].strip()
    if not name:
        return None
    if len(name) <= MAX_ARTIFACT_NAME_CHARS:
        return name
    words: list[str] = []
    total = 0
    for word in name.split():
        next_total = total + len(word) + (1 if words else 0)
        if next_total > MAX_ARTIFACT_NAME_CHARS:
            break
        words.append(word)
        total = next_total
    return " ".join(words) or name[:MAX_ARTIFACT_NAME_CHARS].rstrip()

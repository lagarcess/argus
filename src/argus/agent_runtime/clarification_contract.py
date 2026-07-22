from __future__ import annotations

from typing import Any, Literal

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.simplification_option_contract import simplification_option_kind
from argus.agent_runtime.state.models import StrategySummary

OFFLINE_CLARIFICATION_FALLBACK = recovery_message(
    "clarification_generation_unavailable",
    language="en",
)

ClarificationPromptSource = Literal["llm_generated", "degraded_fallback"]


def offline_clarification_fallback(
    *,
    language: str | None = None,
    response_intent: dict[str, Any] | None = None,
    strategy: StrategySummary | dict[str, Any] | None = None,
) -> str:
    intent_question = intent_clarification_fallback(
        language=language,
        response_intent=response_intent,
        strategy=strategy,
    )
    if intent_question:
        return intent_question
    return recovery_message(
        "clarification_generation_unavailable",
        language=language,
    )


def typed_clarification_contract(
    *,
    response_intent: dict[str, Any] | None,
    requested_field: str | None = None,
    strategy: StrategySummary | dict[str, Any] | None = None,
    prompt_source: ClarificationPromptSource = "degraded_fallback",
) -> dict[str, Any] | None:
    if not isinstance(response_intent, dict):
        return None
    kind = response_intent.get("kind")
    if kind == "coverage_recovery":
        options = _typed_options(response_intent)
        coverage = _coverage_facts(response_intent)
        if not options or coverage is None:
            return None
        return {
            "kind": "coverage_recovery",
            "reason_code": coverage["code"],
            "prompt_source": prompt_source,
            "requested_field": None,
            "requested_fields": _requested_fields(response_intent),
            "semantic_needs": _semantic_needs(response_intent),
            "payload": {
                "strategy": _strategy_payload(response_intent, strategy),
                "coverage": coverage,
            },
            "options": options,
        }
    if kind == "unsupported_recovery":
        options = _typed_options(response_intent)
        if not options:
            return None
        semantic_needs = _semantic_needs(response_intent)
        return {
            "kind": "unsupported_recovery",
            "reason_code": _unsupported_reason_code(response_intent),
            "prompt_source": prompt_source,
            "requested_field": requested_field or "unsupported_constraints",
            "requested_fields": _requested_fields(response_intent)
            or ["unsupported_constraints"],
            "semantic_needs": semantic_needs,
            "payload": {
                "strategy": _strategy_payload(response_intent, strategy),
                "raw_value": _unsupported_raw_value(response_intent),
            },
            "options": options,
        }
    if kind != "clarification":
        return None
    semantic_needs = _semantic_needs(response_intent)
    requested_fields = _requested_fields(response_intent)
    requested = requested_field or (requested_fields[0] if requested_fields else None)
    return {
        "kind": "clarification",
        "reason_code": _clarification_reason_code(
            requested_field=requested,
            semantic_needs=semantic_needs,
        ),
        "prompt_source": prompt_source,
        "requested_field": requested,
        "requested_fields": requested_fields,
        "semantic_needs": semantic_needs,
        "payload": {"strategy": _strategy_payload(response_intent, strategy)},
        "options": [],
    }


def _coverage_facts(response_intent: dict[str, Any]) -> dict[str, Any] | None:
    facts = response_intent.get("facts")
    if not isinstance(facts, dict):
        return None
    coverage = facts.get("coverage")
    if not isinstance(coverage, dict):
        return None
    code = coverage.get("code")
    if not isinstance(code, str) or not code:
        return None
    return dict(coverage)


def intent_clarification_fallback(
    *,
    language: str | None,
    response_intent: dict[str, Any] | None,
    strategy: StrategySummary | dict[str, Any] | None,
) -> str | None:
    if not isinstance(response_intent, dict):
        return None
    if response_intent.get("kind") == "coverage_recovery":
        coverage = _coverage_facts(response_intent)
        code = coverage.get("code") if coverage is not None else None
        _ = language
        if code == "no_common_data_window":
            return (
                "Those assets and the benchmark do not share a usable data window. "
                "Would you like to change the dates, an asset, or the benchmark?"
            )
        return (
            "The shared data window is not sufficient for a trustworthy test. "
            "Would you like to change the dates, an asset, or the benchmark?"
        )
    if response_intent.get("kind") == "unsupported_recovery":
        return _unsupported_recovery_fallback(
            language=language,
            response_intent=response_intent,
            strategy=strategy,
        )
    if response_intent.get("kind") != "clarification":
        return None
    needs = response_intent.get("semantic_needs")
    if not isinstance(needs, list) or not needs:
        return None
    symbol = _primary_symbol(strategy)
    _ = language
    if "period" in needs:
        return f"What date window should I use{_en_asset_suffix(symbol)}?"
    if "asset_target" in needs:
        return "Which asset should I test?"
    if "assumption" in needs:
        return f"What assumption should I adjust{_en_asset_suffix(symbol)}?"
    if "sizing_amount" in needs and "schedule" in needs:
        return "How much should each purchase be, and how often should it happen?"
    if "sizing_amount" in needs:
        return "How much should I use?"
    if "schedule" in needs:
        return "How often should the purchases happen?"
    if "rule_definition" in needs:
        return "What entry or exit rule should I test?"
    if "refinement" in needs:
        return "What would you like to change?"
    return None


def _unsupported_recovery_fallback(
    *,
    language: str | None,
    response_intent: dict[str, Any],
    strategy: StrategySummary | dict[str, Any] | None,
) -> str | None:
    _ = language
    if _unsupported_reason_code(response_intent) == "future_performance":
        options = _option_labels(response_intent)
        offer = (
            f" Which direction should I take: {_join_options(options)}?"
            if options
            else " What historical period would you like to examine?"
        )
        return (
            "I cannot predict future performance. I can test how the same idea "
            f"performed over a historical period instead.{offer}"
        )
    if _unsupported_reason_code(response_intent) == "unsupported_time_granularity":
        raw_value = _unsupported_raw_value(response_intent)
        if raw_value:
            return (
                f"{raw_value} is not a supported bar size. "
                "Choose daily or 1-hour bars."
            )
        return "That bar size is not supported. Choose daily or 1-hour bars."
    options = _option_labels(response_intent)
    if not options:
        return None
    raw_value = _unsupported_raw_value(response_intent)
    symbol = _primary_symbol(strategy)
    joined_options = _join_options(options)
    subject = raw_value or "That rule"
    symbol_suffix = f" for {symbol}" if symbol else ""
    return (
        f"{subject} does not define when to buy or sell{symbol_suffix} on its own. "
        f"Which supported direction should I use: {joined_options}?"
    )


def _option_labels(response_intent: dict[str, Any]) -> list[str]:
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    labels: list[str] = []
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        label = _fallback_option_label(option)
        if label is None:
            continue
        if label not in labels:
            labels.append(label)
    return labels[:3]


def _typed_options(response_intent: dict[str, Any]) -> list[dict[str, Any]]:
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, option in enumerate(raw_options):
        if not isinstance(option, dict):
            continue
        replacement_values = option.get("replacement_values")
        explicit_id = option.get("id")
        option_id = (
            simplification_option_kind(replacement_values)
            or (
                explicit_id.strip()
                if isinstance(explicit_id, str) and explicit_id.strip()
                else None
            )
            or f"option_{index}"
        )
        if option_id in seen:
            continue
        seen.add(option_id)
        typed_option: dict[str, Any] = {
            "id": option_id,
            "replacement_values": dict(replacement_values)
            if isinstance(replacement_values, dict)
            else {},
        }
        label = option.get("label")
        if isinstance(label, str) and label.strip():
            typed_option["compatibility_label"] = label.strip()
        options.append(typed_option)
    return options[:3]


def _unsupported_raw_value(response_intent: dict[str, Any]) -> str | None:
    facts = response_intent.get("facts")
    if not isinstance(facts, dict):
        return None
    constraints = facts.get("unsupported_constraints")
    if not isinstance(constraints, list):
        return None
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        raw_value = constraint.get("raw_value")
        if not isinstance(raw_value, str):
            continue
        value = raw_value.strip()
        if value and not _looks_like_internal_code(value):
            return value
    return None


def _unsupported_reason_code(response_intent: dict[str, Any]) -> str:
    facts = response_intent.get("facts")
    if not isinstance(facts, dict):
        return "unsupported_constraint"
    constraints = facts.get("unsupported_constraints")
    if not isinstance(constraints, list):
        return "unsupported_constraint"
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        category = constraint.get("category")
        if isinstance(category, str) and category.strip():
            return category.strip()
    return "unsupported_constraint"


def _semantic_needs(response_intent: dict[str, Any]) -> list[str]:
    needs = response_intent.get("semantic_needs")
    if not isinstance(needs, list):
        return []
    return [need for need in needs if isinstance(need, str)]


def _requested_fields(response_intent: dict[str, Any]) -> list[str]:
    fields = response_intent.get("requested_fields")
    if not isinstance(fields, list):
        return []
    return [field for field in fields if isinstance(field, str)]


def _clarification_reason_code(
    *,
    requested_field: str | None,
    semantic_needs: list[str],
) -> str:
    base_field = str(requested_field or "").split("[", 1)[0]
    if base_field == "date_range" or "period" in semantic_needs:
        return "missing_period"
    if base_field == "asset_universe" or "asset_target" in semantic_needs:
        return "missing_asset_target"
    if base_field == "assumption" or "assumption" in semantic_needs:
        return "missing_assumption"
    if "sizing_amount" in semantic_needs and "schedule" in semantic_needs:
        return "missing_sizing_amount_schedule"
    if base_field == "capital_amount" or "sizing_amount" in semantic_needs:
        return "missing_sizing_amount"
    if base_field == "cadence" or "schedule" in semantic_needs:
        return "missing_schedule"
    if base_field in {"entry_logic", "exit_logic"} or "rule_definition" in semantic_needs:
        return "missing_rule_definition"
    if "refinement" in semantic_needs:
        return "missing_refinement"
    return "clarification_needed"


def _strategy_payload(
    response_intent: dict[str, Any],
    strategy: StrategySummary | dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    if isinstance(strategy, dict):
        return dict(strategy)
    facts = response_intent.get("facts")
    if isinstance(facts, dict):
        fact_strategy = facts.get("strategy")
        if isinstance(fact_strategy, dict):
            return dict(fact_strategy)
    return {}


def _looks_like_internal_code(value: str) -> bool:
    # raw_value should carry the user's own words; a whitespace-free
    # lowercase snake_case token is an internal reason code and must never
    # render in prose. Uppercase underscore tokens (BTC_USDT, BRK_B) are
    # user-typed symbols and stay quotable.
    return (
        "_" in value
        and value == value.lower()
        and not any(character.isspace() for character in value)
    )


def _fallback_option_label(option: dict[str, Any]) -> str | None:
    kind = simplification_option_kind(option.get("replacement_values"))
    if kind == "rsi_threshold":
        return "Use a supported RSI threshold rule"
    if kind == "buy_and_hold":
        return "Compare with buy and hold"
    if kind == "moving_average_crossover":
        return "Use a supported moving-average crossover"
    label = option.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return None


def _join_options(options: list[str]) -> str:
    if len(options) <= 1:
        return options[0] if options else ""
    if len(options) == 2:
        return " or ".join(options)
    return f"{', '.join(options[:-1])}, or {options[-1]}"


def _primary_symbol(strategy: StrategySummary | dict[str, Any] | None) -> str | None:
    assets: Any = None
    if isinstance(strategy, StrategySummary):
        assets = strategy.asset_universe
    elif isinstance(strategy, dict):
        assets = strategy.get("asset_universe")
    if not isinstance(assets, list):
        return None
    for item in assets:
        symbol = str(item or "").strip().upper()
        if symbol:
            return symbol
    return None


def _en_asset_suffix(symbol: str | None) -> str:
    return f" for {symbol}" if symbol else ""

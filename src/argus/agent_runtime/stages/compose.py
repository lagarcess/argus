from __future__ import annotations

from argus.agent_runtime.state.models import ResponseIntent, RunState, StrategySummary


def compose_response_intent(state: RunState) -> str | None:
    intent = state.response_intent
    if intent is None:
        return None
    if intent.kind == "beginner_guidance":
        return (
            "We can do this conversationally. Tell me an asset you are curious "
            "about and a rough timeframe, or ask me to explain a market term first. "
            "If you already have an idea, say it in one sentence and I will shape it."
        )
    if intent.kind == "ambiguity_check":
        return (
            "I can keep working on the current idea or start a new backtest. "
            "Which direction do you want?"
        )
    if intent.kind == "optional_settings":
        choices = intent.facts.get("optional_parameter_choices", [])
        labels = _human_list(
            [
                _human_field_name(str(choice))
                for choice in choices
                if isinstance(choice, str)
            ]
        )
        if labels:
            return (
                f"I can use defaults, or adjust {labels} before we run it. "
                "Do you want to change one of those?"
            )
        return "I can use defaults for the remaining assumptions. Do you want to run it?"
    if intent.kind == "unsupported_recovery":
        return _compose_unsupported_recovery(intent)
    if intent.kind == "clarification":
        return _compose_clarification(intent)
    return None


def should_prefer_composed_intent(state: RunState) -> bool:
    intent = state.response_intent
    if intent is None:
        return False
    if intent.kind != "clarification":
        return False
    return "rule_definition" in intent.semantic_needs


def _compose_clarification(intent: ResponseIntent) -> str:
    strategy = _strategy_from_intent(intent)
    needs = list(dict.fromkeys(intent.semantic_needs))
    context = _strategy_context(strategy)

    if needs == ["asset_target"]:
        return f"{context}What asset should I use?"
    if needs == ["period"]:
        return f"{context}What time period should I test?"
    if needs == ["sizing_amount"]:
        return f"{context}How much should each recurring purchase be?"
    if needs == ["rule_definition"]:
        if _strategy_has_rule_detail(strategy):
            return (
                f"{context}I have the rule direction, but the executable version "
                "needs to be simplified into one supported rule. I can use a "
                "percentage move, a supported moving-average crossover, an RSI "
                "threshold, or keep the full rule as a draft. Which direction "
                "should I take?"
            )
        return (
            f"{context}I need to turn the idea into a specific testable rule. "
            "Do you want to define it as a percentage move, a supported "
            "moving-average crossover, an RSI threshold, or keep drafting the "
            "full rule?"
        )
    if set(needs) == {"asset_target", "period"}:
        return f"{context}What asset and time period should I use?"
    if set(needs) == {"period", "rule_definition"}:
        return (
            f"{context}What time period should I test, and what specific "
            "testable rule should define the signal? For example: a percentage "
            "move, a moving-average crossover, price above an average, or an "
            "RSI threshold."
        )
    if set(needs) == {"sizing_amount", "period"}:
        return (
            f"{context}How much should each recurring purchase be, and what "
            "time period should I test?"
        )
    if set(needs) == {"asset_target", "sizing_amount"}:
        return f"{context}What asset should I use, and how much should each purchase be?"
    if needs:
        questions = [_question_for_need(need) for need in needs]
        return f"{context}{' '.join(question for question in questions if question)}"
    return f"{context}I need one more detail before I can turn this into a " "backtest."


def _compose_unsupported_recovery(intent: ResponseIntent) -> str:
    constraints = intent.facts.get("unsupported_constraints", [])
    explanation = ""
    if isinstance(constraints, list) and constraints:
        first = constraints[0]
        if isinstance(first, dict):
            explanation = str(first.get("explanation") or "").strip()
    if not explanation:
        explanation = "I understand the idea, but part of it is not executable yet."
    labels = [
        _human_option_label(str(option.get("label", "")))
        for option in intent.options
        if isinstance(option, dict) and str(option.get("label", "")).strip()
    ]
    if labels:
        return (
            f"{explanation} I can {_human_list(labels)}. Which direction should I take?"
        )
    return f"{explanation} I can help simplify it into something runnable."


def _strategy_from_intent(intent: ResponseIntent) -> StrategySummary:
    raw = intent.facts.get("strategy")
    if isinstance(raw, StrategySummary):
        return raw
    if isinstance(raw, dict):
        return StrategySummary.model_validate(raw)
    return StrategySummary()


def _strategy_context(strategy: StrategySummary) -> str:
    strategy_type = strategy.strategy_type or ""
    assets = ", ".join(strategy.asset_universe)
    if strategy_type == "buy_and_hold":
        if assets:
            return f"I understand this as a simple buy-and-hold test for {assets}. "
        return "I understand this as a simple buy-and-hold test. "
    if strategy_type == "dca_accumulation":
        if assets:
            return f"I read this as recurring buys for {assets}. "
        return "I read this as recurring buys. "
    if strategy_type == "indicator_threshold":
        if assets:
            return f"I read this as an indicator-rule test for {assets}. "
        return "I read this as an indicator-rule test. "
    if strategy_type == "signal_strategy":
        if assets:
            return f"I read this as a signal-rule test for {assets}. "
        return "I read this as a signal-rule test. "
    if assets:
        return f"I understand the idea for {assets}. "
    return "I understand the direction. "


def _strategy_has_rule_detail(strategy: StrategySummary) -> bool:
    return any(
        value not in (None, "", [], {})
        for value in (
            strategy.entry_logic,
            strategy.exit_logic,
            strategy.entry_rule,
            strategy.exit_rule,
            strategy.rule_spec,
        )
    )


def _question_for_need(need: str) -> str:
    questions = {
        "asset_target": "What asset should I use?",
        "sizing_amount": "How much should each recurring purchase be?",
        "schedule": "How often should the purchases happen?",
        "period": "What time period should I test?",
        "rule_definition": "What specific rule should I test?",
        "assumption": "Which assumption do you want to change?",
        "simplification_choice": "Which simplification should I use?",
    }
    return questions.get(need, "")


def _human_field_name(value: str) -> str:
    labels = {
        "initial_capital": "starting capital",
        "timeframe": "bar timeframe",
        "fees": "fees",
        "slippage": "slippage",
    }
    return labels.get(value, value.replace("_", " "))


def _human_option_label(label: str) -> str:
    normalized = label.strip().lower().replace("_", " ")
    labels = {
        "max available": "use the maximum available history",
        "maximum available": "use the maximum available history",
        "since ipo": "start at the IPO date",
        "run recurring buys only": "run the recurring-buy simulation only",
        "adjust recurring contribution": "adjust the recurring contribution",
        "use buy and hold with starting capital": (
            "switch to buy and hold with the starting capital"
        ),
        "use a supported rsi threshold rule": "use a supported RSI threshold rule",
        "compare with buy and hold": "compare with buy and hold",
        "use a supported moving-average crossover": (
            "use a supported moving-average crossover"
        ),
    }
    return labels.get(normalized, label.strip().replace("_", " "))


def _human_list(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} or {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", or {cleaned[-1]}"

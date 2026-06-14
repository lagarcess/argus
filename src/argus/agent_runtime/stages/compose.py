from __future__ import annotations

from argus.agent_runtime.recovery_messages import Language, resolve_recovery_language
from argus.agent_runtime.state.models import (
    ArtifactActionRecoveryFacts,
    ResponseIntent,
    RunState,
    StrategySummary,
)
from pydantic import ValidationError


def compose_response_intent(state: RunState) -> str | None:
    intent = state.response_intent
    if intent is None:
        return None
    language = _intent_language(intent)
    if intent.kind == "beginner_guidance":
        return _llm_composition_unavailable_recovery(language=language)
    if intent.kind == "ambiguity_check":
        return _ambiguity_check_message(language=language)
    if intent.kind == "optional_settings":
        choices = intent.facts.get("optional_parameter_choices", [])
        labels = _human_list(
            [
                _human_field_name(str(choice), language=language)
                for choice in choices
                if isinstance(choice, str)
            ],
            language=language,
        )
        if labels:
            if language == "es-419":
                return (
                    f"Puedo usar los valores predeterminados o ajustar {labels} "
                    "antes de ejecutarlo. ¿Quieres cambiar alguno?"
                )
            return (
                f"I can use defaults, or adjust {labels} before we run it. "
                "Do you want to change one of those?"
            )
        if language == "es-419":
            return (
                "Puedo usar los valores predeterminados para los supuestos "
                "restantes. ¿Quieres ejecutarlo?"
            )
        return "I can use defaults for the remaining assumptions. Do you want to run it?"
    if intent.kind == "artifact_action_recovery":
        return _compose_artifact_action_recovery(intent, language=language)
    if intent.kind == "unsupported_recovery":
        return _compose_unsupported_recovery(intent, language=language)
    if intent.kind == "clarification":
        return _compose_clarification(intent, language=language)
    return None


def should_prefer_composed_intent(state: RunState) -> bool:
    intent = state.response_intent
    if intent is None:
        return False
    if intent.kind == "artifact_action_recovery":
        return True
    if intent.kind == "unsupported_recovery":
        return _should_compose_unsupported_recovery(intent)
    if intent.kind != "clarification":
        return False
    strategy = _strategy_from_intent(intent)
    if strategy.strategy_type != "dca_accumulation":
        return False
    needs = set(intent.semantic_needs)
    missing_fields = set(state.missing_required_fields)
    return (
        {"sizing_amount", "schedule"}.issubset(needs)
        and {"capital_amount", "cadence"}.issubset(missing_fields)
        and not {"asset_universe", "date_range"}.intersection(missing_fields)
    )


def _should_compose_unsupported_recovery(intent: ResponseIntent) -> bool:
    strategy = _strategy_from_intent(intent)
    if strategy.strategy_type != "dca_accumulation":
        return False
    if not _has_dca_runnable_execution_fields(strategy):
        return False
    constraints = intent.facts.get("unsupported_constraints", [])
    if not isinstance(constraints, list):
        return False
    return any(
        isinstance(constraint, dict)
        and constraint.get("category") == "unsupported_dca_starting_principal"
        for constraint in constraints
    )


def _has_dca_runnable_execution_fields(strategy: StrategySummary) -> bool:
    return bool(
        strategy.asset_universe
        and strategy.date_range not in (None, "", [], {})
        and strategy.capital_amount is not None
        and _has_dca_cadence(strategy)
    )


def _intent_language(intent: ResponseIntent) -> Language:
    raw_language = intent.facts.get("language")
    if not isinstance(raw_language, str) or not raw_language.strip():
        strategy = _strategy_from_intent(intent)
        raw_language = strategy.extra_parameters.get("language")
    return resolve_recovery_language(raw_language if isinstance(raw_language, str) else None)


def _llm_composition_unavailable_recovery(*, language: Language) -> str:
    if language == "es-419":
        return (
            "No pude darle forma con claridad en este momento. Dame un activo y "
            "una ventana aproximada, y lo convertiré en la prueba histórica "
            "ejecutable más cercana."
        )
    return (
        "I couldn't shape that cleanly just now. Try giving me an asset and rough "
        "time window, and I'll turn it into the closest runnable historical test."
    )


def _ambiguity_check_message(*, language: Language) -> str:
    if language == "es-419":
        return (
            "Puedo seguir trabajando con la idea actual o empezar un backtest "
            "nuevo. ¿Qué prefieres?"
        )
    return (
        "I can keep working on the current idea or start a new backtest. "
        "Which direction do you want?"
    )


def _compose_clarification(intent: ResponseIntent, *, language: Language) -> str:
    strategy = _strategy_from_intent(intent)
    needs = list(dict.fromkeys(intent.semantic_needs))
    context = _strategy_context(strategy, language=language)

    if needs == ["asset_target"]:
        return (
            f"{context}¿Qué activo debería usar como base?"
            if language == "es-419"
            else f"{context}Which asset should anchor the test?"
        )
    if needs == ["period"]:
        return (
            f"{context}¿Qué rango de fechas debería usar?"
            if language == "es-419"
            else f"{context}Which date window should I use?"
        )
    if needs == ["sizing_amount"]:
        dca_question = _dca_execution_question(strategy, language=language)
        if dca_question:
            return f"{context}{dca_question}"
        return (
            f"{context}¿Cuánto debería ser cada compra recurrente?"
            if language == "es-419"
            else f"{context}How much should each recurring purchase be?"
        )
    if set(needs) == {"sizing_amount", "schedule"}:
        dca_question = _dca_execution_question(strategy, language=language)
        if dca_question:
            return f"{context}{dca_question}"
        if language == "es-419":
            return (
                f"{context}¿Cuánto debería ser cada compra recurrente y cada "
                "cuánto deberían ocurrir esas compras?"
            )
        return (
            f"{context}How much should each recurring purchase be, and how often "
            "should those purchases happen?"
        )
    if needs == ["rule_definition"]:
        if _strategy_has_rule_detail(strategy):
            if language == "es-419":
                return (
                    f"{context}La idea está clara, pero la versión ejecutable "
                    "necesita simplificarse en una regla compatible. Puedo usar "
                    "un movimiento porcentual, un cruce de medias móviles "
                    "compatible, un umbral RSI, o mantener la regla completa "
                    "como borrador. ¿Qué prefieres?"
                )
            return (
                f"{context}The idea is clear, but the runnable version needs to "
                "be simplified into one supported rule. I can use a "
                "percentage move, a supported moving-average crossover, an RSI "
                "threshold, or keep the full rule as a draft. Which direction "
                "should I take?"
            )
        if language == "es-419":
            return (
                f"{context}Necesito convertir la idea en una regla específica "
                "que pueda probar. ¿Quieres definirla como un movimiento "
                "porcentual, un cruce de medias móviles compatible, un umbral "
                "RSI, o mantener la regla completa como borrador?"
            )
        return (
            f"{context}I need to turn the idea into a specific testable rule. "
            "Do you want to define it as a percentage move, a supported "
            "moving-average crossover, an RSI threshold, or keep drafting the "
            "full rule?"
        )
    if set(needs) == {"asset_target", "period"}:
        return (
            f"{context}¿Con qué activo debería probarlo y qué rango de fechas "
            "debería usar?"
            if language == "es-419"
            else f"{context}What should I test it on, and what date window should I use?"
        )
    if set(needs) == {"asset_target", "period", "sizing_amount", "schedule"}:
        if language == "es-419":
            return (
                f"{context}Para probarlo, dime el activo, el rango de fechas, "
                "el monto de cada compra recurrente y la cadencia de compra."
            )
        return (
            f"{context}To test it, tell me the asset, date window, recurring "
            "purchase amount, and purchase cadence."
        )
    if set(needs) == {"period", "rule_definition"}:
        if language == "es-419":
            return (
                f"{context}¿Qué rango de fechas debería usar y qué regla "
                "específica debería definir la señal? Por ejemplo: un "
                "movimiento porcentual, un cruce de medias móviles, precio por "
                "encima de una media, o un umbral RSI."
            )
        return (
            f"{context}Which date window should I use, and what specific "
            "testable rule should define the signal? For example: a percentage "
            "move, a moving-average crossover, price above an average, or an "
            "RSI threshold."
        )
    if set(needs) == {"sizing_amount", "period"}:
        if language == "es-419":
            return (
                f"{context}¿Cuánto debería ser cada compra recurrente y qué "
                "periodo debería probar?"
            )
        return (
            f"{context}How much should each recurring purchase be, and what "
            "time period should I test?"
        )
    if set(needs) == {"asset_target", "sizing_amount"}:
        return (
            f"{context}¿Qué activo debería usar y cuánto debería ser cada compra?"
            if language == "es-419"
            else f"{context}What asset should I use, and how much should each purchase be?"
        )
    if needs:
        questions = [_question_for_need(need, language=language) for need in needs]
        return f"{context}{' '.join(question for question in questions if question)}"
    if language == "es-419":
        return (
            f"{context}No pude identificar exactamente qué falta. Dime el "
            "activo, el rango de fechas o el detalle de la regla que quieres "
            "usar, y mantendré el borrador intacto."
        )
    return (
        f"{context}I couldn't identify the exact missing input. Tell me the "
        "asset, date window, or rule detail you want to use, and I'll keep the "
        "draft intact."
    )


def _compose_unsupported_recovery(
    intent: ResponseIntent,
    *,
    language: Language,
) -> str:
    constraints = intent.facts.get("unsupported_constraints", [])
    explanation = ""
    if isinstance(constraints, list) and constraints:
        first = constraints[0]
        if isinstance(first, dict):
            explanation = _unsupported_explanation(first, language=language)
    if not explanation:
        explanation = (
            "Entiendo la idea, pero una parte todavía no es ejecutable."
            if language == "es-419"
            else "I understand the idea, but part of it is not executable yet."
        )
    labels = [
        _human_option_label(str(option.get("label", "")), language=language)
        for option in intent.options
        if isinstance(option, dict) and str(option.get("label", "")).strip()
    ]
    if labels:
        if language == "es-419":
            return (
                f"{explanation} Puedo {_human_list(labels, language=language)}. "
                "¿Qué opción prefieres?"
            )
        return (
            f"{explanation} I can {_human_list(labels, language=language)}. "
            "Which direction should I take?"
        )
    if language == "es-419":
        return f"{explanation} Puedo ayudarte a simplificarla en algo ejecutable."
    return f"{explanation} I can help simplify it into something runnable."


def _unsupported_explanation(
    constraint: dict[str, object],
    *,
    language: Language,
) -> str:
    if language == "es-419":
        category = str(constraint.get("category") or "")
        if category == "unsupported_dca_starting_principal":
            return (
                "Entiendo ese monto como presupuesto o capital total, pero el "
                "backtest DCA actual solo puede ejecutar la contribución recurrente."
            )
    return str(constraint.get("explanation") or "").strip()


def _compose_artifact_action_recovery(
    intent: ResponseIntent,
    *,
    language: Language,
) -> str:
    facts = _artifact_action_recovery_facts(intent)
    if facts is None:
        if language == "es-419":
            return (
                "Esa acción ya no está conectada al estado actual de la "
                "conversación. Usa la acción visible más reciente o dime qué "
                "quieres hacer ahora."
            )
        return (
            "That action is no longer attached to the current conversation state. "
            "Use the latest visible action or tell me what you want to do next."
        )
    if facts.status == "stale":
        if language == "es-419":
            return (
                "Ese reintento pertenece a una ejecución fallida anterior. Usa "
                "la acción de reintento más reciente o confirma la configuración "
                "que quieres ejecutar."
            )
        return (
            "That retry belongs to an older failed run. Use the latest retry action "
            "or confirm the setup you want to run."
        )
    if facts.status == "missing_artifact_id":
        if language == "es-419":
            return (
                "A ese reintento le falta la referencia de la ejecución fallida. "
                "Usa la acción de reintento más reciente o confirma la "
                "configuración que quieres ejecutar."
            )
        return (
            "That retry is missing its failed-run reference. Use the latest retry "
            "action or confirm the setup you want to run."
        )
    if facts.status == "missing_payload":
        if language == "es-419":
            return (
                "No tengo una carga de ejecución fallida para reintentar. Usa de "
                "nuevo la acción visible de ejecutar backtest, o confirma la "
                "estrategia que quieres ejecutar."
            )
        return (
            "I do not have a failed run payload to retry. Use the visible Run "
            "backtest action again, or confirm the strategy you want me to run."
        )
    if facts.status == "non_retryable":
        message = facts.user_safe_message
        if isinstance(message, str) and message.strip():
            if language == "es-419":
                return (
                    "Todavía tengo la configuración fallida, pero volver a "
                    "ejecutar la misma carga encontrará el mismo bloqueo: "
                    f"{message.strip()} Ajusta la regla, el activo o el rango "
                    "de fechas y mantendré la idea intacta."
                )
            return (
                "I still have the failed setup, but rerunning the same payload will "
                f"hit the same blocker: {message.strip()} Adjust the rule, asset, "
                "or date range and I will keep the idea intact."
            )
        if language == "es-419":
            return (
                "Todavía tengo la configuración fallida, pero volver a ejecutar "
                "la misma carga encontrará el mismo bloqueo. Ajusta la regla, el "
                "activo o el rango de fechas y mantendré la idea intacta."
            )
        return (
            "I still have the failed setup, but rerunning the same payload will hit "
            "the same blocker. Adjust the rule, asset, or date range and I will "
            "keep the idea intact."
        )
    if facts.status == "rebuilt_confirmation":
        if language == "es-419":
            return (
                "Todavía tengo esa configuración fallida. Reconstruí el borrador "
                "para que puedas revisar la tarjeta y reintentar cuando estés listo."
            )
        return (
            "I still have that failed setup. I rebuilt the draft so you can review "
            "the card and retry when you are ready."
        )
    if language == "es-419":
        return (
            "Ese reintento ya no está conectado a una ejecución fallida activa. "
            "Usa la acción de reintento más reciente o confirma la configuración "
            "que quieres ejecutar."
        )
    return (
        "That retry is no longer attached to an active failed run. Use the latest "
        "retry action or confirm the setup you want to run."
    )


def _artifact_action_recovery_facts(
    intent: ResponseIntent,
) -> ArtifactActionRecoveryFacts | None:
    try:
        return ArtifactActionRecoveryFacts.model_validate(intent.facts)
    except ValidationError:
        return None


def _strategy_from_intent(intent: ResponseIntent) -> StrategySummary:
    raw = intent.facts.get("strategy")
    if isinstance(raw, StrategySummary):
        return raw
    if isinstance(raw, dict):
        return StrategySummary.model_validate(raw)
    return StrategySummary()


def _strategy_context(strategy: StrategySummary, *, language: Language) -> str:
    strategy_type = strategy.strategy_type or ""
    assets = ", ".join(strategy.asset_universe)
    if language == "es-419":
        if strategy_type == "buy_and_hold":
            if assets:
                return f"Puedo probar comprar y mantener para {assets}. "
            return "Puedo probar una idea de comprar y mantener. "
        if strategy_type == "dca_accumulation":
            if assets:
                return f"Puedo probar compras recurrentes para {assets}. "
            return "Puedo probar una idea de compras recurrentes. "
        if strategy_type == "indicator_threshold":
            if assets:
                return f"Puedo preparar esa idea de indicador para {assets}. "
            return "Puedo preparar esa idea de indicador. "
        if strategy_type == "signal_strategy":
            if assets:
                return f"Puedo preparar esa idea de señal para {assets}. "
            return "Puedo preparar esa idea de señal. "
        if assets:
            return f"Puedo trabajar con la idea para {assets}. "
        return "Entiendo la forma de la idea. "
    if strategy_type == "buy_and_hold":
        if assets:
            return f"I can test buy-and-hold for {assets}. "
        return "I can test a buy-and-hold idea. "
    if strategy_type == "dca_accumulation":
        if assets:
            return f"I can test recurring buys for {assets}. "
        return "I can test a recurring-buy idea. "
    if strategy_type == "indicator_threshold":
        if assets:
            return f"I can set up that indicator idea for {assets}. "
        return "I can set up that indicator idea. "
    if strategy_type == "signal_strategy":
        if assets:
            return f"I can set up that signal idea for {assets}. "
        return "I can set up that signal idea. "
    if assets:
        return f"I can work with the idea for {assets}. "
    return "I understand the shape of the idea. "


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


def _has_total_budget_context(strategy: StrategySummary) -> bool:
    extra_parameters = strategy.extra_parameters or {}
    return any(
        extra_parameters.get(key) not in (None, "", [], {})
        for key in ("initial_capital", "total_capital", "total_budget", "max_budget")
    )


def _dca_execution_question(
    strategy: StrategySummary,
    *,
    language: Language,
) -> str | None:
    if strategy.strategy_type != "dca_accumulation":
        return None
    clauses = (
        ["cuánto debería ser cada compra recurrente"]
        if language == "es-419"
        else ["how much should each recurring purchase be"]
    )
    if not _has_dca_cadence(strategy):
        clauses.append(
            "cada cuánto deberían ocurrir esas compras"
            if language == "es-419"
            else "how often should those purchases happen"
        )
    question = _question_from_clauses(clauses, language=language)
    if _has_total_budget_context(strategy):
        question += (
            " Mantendré el presupuesto total separado del monto por compra."
            if language == "es-419"
            else " I will keep the total budget separate from the per-buy amount."
        )
    return question


def _has_dca_cadence(strategy: StrategySummary) -> bool:
    if strategy.cadence not in (None, "", [], {}):
        return True
    extra_parameters = strategy.extra_parameters or {}
    return extra_parameters.get("cadence") not in (None, "", [], {})


def _question_from_clauses(clauses: list[str], *, language: Language) -> str:
    if not clauses:
        return ""
    if len(clauses) == 1:
        return f"¿{clauses[0].capitalize()}?" if language == "es-419" else f"{clauses[0].capitalize()}?"
    if language == "es-419":
        return f"¿{clauses[0].capitalize()} y {clauses[1]}?"
    return f"{clauses[0].capitalize()}, and {clauses[1]}?"


def _question_for_need(need: str, *, language: Language) -> str:
    if language == "es-419":
        questions = {
            "asset_target": "¿Qué activo debería usar?",
            "sizing_amount": "¿Cuánto debería ser cada compra recurrente?",
            "schedule": "¿Cada cuánto deberían ocurrir las compras?",
            "period": "¿Qué rango de fechas debería usar?",
            "rule_definition": "¿Qué regla específica debería probar?",
            "assumption": "¿Qué supuesto quieres cambiar?",
            "simplification_choice": "¿Qué simplificación debería usar?",
            "refinement": "¿Qué debería cambiar, comparar o poner a prueba ahora?",
        }
        return questions.get(need, "")
    questions = {
        "asset_target": "What asset should I use?",
        "sizing_amount": "How much should each recurring purchase be?",
        "schedule": "How often should the purchases happen?",
        "period": "Which date window should I use?",
        "rule_definition": "What specific rule should I test?",
        "assumption": "Which assumption do you want to change?",
        "simplification_choice": "Which simplification should I use?",
        "refinement": "What should I change, compare, or stress-test next?",
    }
    return questions.get(need, "")


def _human_field_name(value: str, *, language: Language) -> str:
    labels = (
        {
            "initial_capital": "capital inicial",
            "timeframe": "frecuencia de datos",
            "fees": "comisiones",
            "slippage": "deslizamiento",
        }
        if language == "es-419"
        else {
        "initial_capital": "starting capital",
        "timeframe": "bar timeframe",
        "fees": "fees",
        "slippage": "slippage",
    }
    )
    return labels.get(value, value.replace("_", " "))


def _human_option_label(label: str, *, language: Language) -> str:
    normalized = label.strip().lower().replace("_", " ")
    labels = (
        {
            "max available": "usar el máximo historial disponible",
            "maximum available": "usar el máximo historial disponible",
            "since ipo": "empezar en la fecha de IPO",
            "run recurring buys only": "ejecutar solo la simulación de compras recurrentes",
            "adjust recurring contribution": "ajustar la contribución recurrente",
            "use buy and hold with starting capital": (
                "cambiar a comprar y mantener con el capital inicial"
            ),
            "use a supported rsi threshold rule": (
                "usar una regla compatible de umbral RSI"
            ),
            "compare with buy and hold": "comparar con comprar y mantener",
            "use a supported moving-average crossover": (
                "usar un cruce de medias móviles compatible"
            ),
        }
        if language == "es-419"
        else {
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
    )
    fallback = label.strip().replace("_", " ")
    if fallback[:1].isupper() and fallback[1:2].islower():
        fallback = fallback[:1].lower() + fallback[1:]
    return labels.get(normalized, fallback)


def _human_list(values: list[str], *, language: Language) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        connector = "o" if language == "es-419" else "or"
        return f"{cleaned[0]} {connector} {cleaned[1]}"
    connector = "o" if language == "es-419" else "or"
    return ", ".join(cleaned[:-1]) + f", {connector} {cleaned[-1]}"

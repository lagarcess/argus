from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

SUPPORTED_TEMPLATES = set(STRATEGY_CAPABILITIES.keys())
SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}
TEMPLATE_ALIASES: list[tuple[str, str]] = []
for cap in STRATEGY_CAPABILITIES.values():
    for alias in cap.aliases:
        TEMPLATE_ALIASES.append((cap.template, alias))
NON_SYMBOLS = {
    "WHAT",
    "IF",
    "WHENEVER",
    "WHEN",
    "BOUGHT",
    "BUY",
    "DIPPED",
    "HARD",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "STOCK",
    "CRYPTO",
}
COMMON_NAMES = {
    "TESLA": "TSLA",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
}


STARTER_PROMPTS = {
    "learn_basics": [
        "How do I start investing?",
        "What is a moving average?",
        "Explain RSI to me simply",
        "How do I test a stock idea?",
    ],
    "test_stock_idea": [
        "Backtest buying Apple dips",
        "How would Tesla perform in a crash?",
        "Is Nvidia overvalued right now?",
        "Show me MSFT momentum",
    ],
    "build_passive_strategy": [
        "DCA into SPY every month",
        "Compare index funds vs stocks",
        "Building a retirement portfolio",
        "Safe long-term strategies",
    ],
    "explore_crypto": [
        "Backtest Bitcoin halvings",
        "Should I buy ETH or BTC?",
        "Crypto momentum breakout",
        "DCA into Bitcoin strategy",
    ],
    "surprise_me": [
        "Show me something interesting",
        "Top performing tech stocks",
        "Best crypto strategy lately",
        "High risk high reward ideas",
    ],
}


def get_starter_prompts(primary_goal: str | None) -> list[str]:
    """Return 3-4 personalized prompts based on primary goal."""
    goal = primary_goal if primary_goal in STARTER_PROMPTS else "surprise_me"
    return STARTER_PROMPTS[goal]


class SlotValue(BaseModel):
    value: Any = None
    source: Literal["user_supplied", "history_inferred", "backend_default", "missing"]
    confidence: float = 1.0


class StrategyIntent(BaseModel):
    template: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    asset_class: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    symbols: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    timeframe: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    start_date: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    end_date: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    starting_capital: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    benchmark_symbol: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    parameters: dict[str, SlotValue] = Field(default_factory=dict)


class StrategyExtraction(BaseModel):
    template: str | None = None
    asset_class: Literal["equity", "crypto"] | None = None
    symbols: list[str] = Field(default_factory=list)
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    benchmark_symbol: str | None = None
    starting_capital: float | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ChatOrchestrationDecision(BaseModel):
    intent: Literal[
        "run_backtest",
        "answer",
        "clarify",
        "onboarding_prompt",
        "education",
        "unsupported_request",
    ]
    assistant_message: str
    strategy_intent: StrategyIntent | None = None
    title_suggestion: str | None = None


class StrategyPlanDecision(BaseModel):
    action: Literal["ask_clarification", "run_backtest", "unsupported"]
    missing_fields: list[str] = Field(default_factory=list)
    message: str | None = None


class NameSuggestion(BaseModel):
    name: str


def build_strategy_intent(
    extraction: StrategyExtraction, history: list[dict[str, str]] | None = None
) -> StrategyIntent:
    """Assess where each parameter came from to guide readiness decisions."""
    history = history or []

    def get_source(
        field_name: str, value: Any
    ) -> Literal["user_supplied", "history_inferred", "backend_default", "missing"]:
        if value is None or (isinstance(value, list) and not value):
            return "missing"

        # Check if the field was mentioned in the last user message
        last_user_msg = next(
            (m["content"].upper() for m in reversed(history) if m["role"] == "user"), ""
        )

        # Symbols check
        if field_name == "symbols" and isinstance(value, list) and value:
            if any(s.upper() in last_user_msg for s in value):
                return "user_supplied"
            return "history_inferred"

        # Template check
        if field_name == "template":
            if value.upper() in last_user_msg:
                return "user_supplied"
            return "history_inferred"

        # Timeframe/Dates check
        if field_name in ["timeframe", "start_date", "end_date"]:
            if value.upper() in last_user_msg:
                return "user_supplied"
            return "history_inferred"

        # Parameters check
        if field_name.startswith("param:"):
            if value and str(value).upper() in last_user_msg:
                return "user_supplied"
            # Cadence special check
            if field_name == "param:dca_cadence" and any(
                kw in last_user_msg
                for kw in [
                    "DAILY",
                    "WEEKLY",
                    "MONTHLY",
                    "DIARIA",
                    "SEMANAL",
                    "MENSUAL",
                ]
            ):
                return "user_supplied"
            return "history_inferred"

        return "backend_default"

    # Convert parameters to SlotValues
    param_slots = {}
    for k, v in (extraction.parameters or {}).items():
        param_slots[k] = SlotValue(
            value=v, source=get_source(f"param:{k}", v)
        )

    return StrategyIntent(
        template=SlotValue(
            value=extraction.template, source=get_source("template", extraction.template)
        ),
        asset_class=SlotValue(
            value=extraction.asset_class or "equity", source="backend_default"
        ),
        symbols=SlotValue(
            value=extraction.symbols, source=get_source("symbols", extraction.symbols)
        ),
        timeframe=SlotValue(
            value=extraction.timeframe,
            source=get_source("timeframe", extraction.timeframe),
        ),
        start_date=SlotValue(
            value=extraction.start_date,
            source=get_source("start_date", extraction.start_date),
        ),
        end_date=SlotValue(
            value=extraction.end_date, source=get_source("end_date", extraction.end_date)
        ),
        benchmark_symbol=SlotValue(
            value=extraction.benchmark_symbol, source="backend_default"
        ),
        starting_capital=SlotValue(
            value=extraction.starting_capital or 10000, source="backend_default"
        ),
        parameters=param_slots,
    )


def merge_intent(
    current: StrategyIntent, previous: StrategyIntent | None
) -> StrategyIntent:
    if previous is None:
        return current

    def pick(cur: SlotValue, old: SlotValue) -> SlotValue:
        return cur if cur.source != "missing" else old

    merged_params = {**previous.parameters}
    for k, v in current.parameters.items():
        if v.source != "missing":
            merged_params[k] = v

    return StrategyIntent(
        template=pick(current.template, previous.template),
        asset_class=pick(current.asset_class, previous.asset_class),
        symbols=pick(current.symbols, previous.symbols),
        timeframe=pick(current.timeframe, previous.timeframe),
        start_date=pick(current.start_date, previous.start_date),
        end_date=pick(current.end_date, previous.end_date),
        starting_capital=pick(current.starting_capital, previous.starting_capital),
        benchmark_symbol=pick(current.benchmark_symbol, previous.benchmark_symbol),
        parameters=merged_params,
    )





def _resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def _heuristic_extract(message: str) -> dict[str, Any]:
    upper = message.upper()
    symbols = [symbol for name, symbol in COMMON_NAMES.items() if name in upper]
    symbols.extend(
        token
        for token in re.findall(r"\b[A-Z]{2,5}\b", upper)
        if token not in NON_SYMBOLS and token not in symbols
    )

    template = None
    lower = message.lower()
    for candidate, alias in TEMPLATE_ALIASES:
        if alias in lower:
            template = candidate
            break

    asset_class: Literal["equity", "crypto"] = (
        "crypto"
        if any(symbol in {"BTC", "ETH", "SOL"} for symbol in symbols)
        else "equity"
    )
    return {
        "template": template,
        "asset_class": asset_class,
        "symbols": symbols[:5],
        "parameters": {},
    }


def build_clarification_message(
    missing_fields: list[str],
    capability: StrategyCapability | None,
    language: str | None,
) -> str:
    """Build a natural language question asking for missing information."""
    is_es = _resolve_language(language) == "es-419"

    if "template" in missing_fields:
        return (
            "¿Qué tipo de estrategia te gustaría probar? Por ejemplo, DCA o Cruce de Medias Móviles."
            if is_es
            else "What kind of strategy would you like to test? For example, DCA or Moving Average Crossover."
        )

    if "symbols" in missing_fields:
        return (
            "¿Sobre qué activos quieres probar la estrategia? Por ejemplo, AAPL o BTC."
            if is_es
            else "Which symbols do you want to test the strategy on? For example, AAPL or BTC."
        )

    # For parameters, use registry display names if possible
    field = missing_fields[0]
    param_spec = capability.parameters.get(field) if capability else None
    display_name = param_spec.key if param_spec else field

    if field == "dca_cadence":
        return (
            "¿Con qué frecuencia quieres que Argus compre: diariamente, semanalmente o mensualmente?"
            if is_es
            else "How often do you want Argus to buy: daily, weekly, or monthly?"
        )

    return (
        f"Necesito un poco más de información sobre {display_name} para continuar."
        if is_es
        else f"I need a bit more information about {display_name} to continue."
    )


def plan_strategy_action(
    intent: StrategyIntent, language: str | None
) -> StrategyPlanDecision:
    """Decide if a strategy is ready to run or needs clarification."""
    template_val = intent.template.value
    if not template_val or intent.template.source == "missing":
        return StrategyPlanDecision(
            action="ask_clarification",
            missing_fields=["template"],
            message=build_clarification_message(["template"], None, language),
        )

    template_str = str(template_val)
    if template_str not in STRATEGY_CAPABILITIES:
        # Check aliases
        found_cap = None
        for cap in STRATEGY_CAPABILITIES.values():
            if template_str.lower() in [a.lower() for a in cap.aliases]:
                found_cap = cap
                break
        
        if not found_cap:
            return StrategyPlanDecision(
                action="ask_clarification",
                missing_fields=["template"],
                message=build_clarification_message(["template"], None, language),
            )
        template_str = found_cap.template

    capability = STRATEGY_CAPABILITIES[template_str]

    if not intent.symbols.value or intent.symbols.source == "missing":
        return StrategyPlanDecision(
            action="ask_clarification",
            missing_fields=["symbols"],
            message=build_clarification_message(["symbols"], capability, language),
        )

    missing_params = []
    for key, spec in capability.parameters.items():
        slot = intent.parameters.get(key)
        if spec.policy == "clarify_if_missing" and (slot is None or slot.source == "missing"):
            missing_params.append(key)

    if missing_params:
        return StrategyPlanDecision(
            action="ask_clarification",
            missing_fields=missing_params,
            message=build_clarification_message(missing_params, capability, language),
        )

    return StrategyPlanDecision(action="run_backtest")


def compile_backtest_payload(intent: StrategyIntent) -> dict[str, object]:
    """Compile a StrategyIntent into a final backtest payload."""
    template_val = intent.template.value
    template_str = str(template_val)

    # Resolve template from aliases if needed
    if template_str not in STRATEGY_CAPABILITIES:
        for cap in STRATEGY_CAPABILITIES.values():
            if template_str.lower() in [a.lower() for a in cap.aliases]:
                template_str = cap.template
                break

    capability = STRATEGY_CAPABILITIES[template_str]

    parameters = {}
    for key, spec in capability.parameters.items():
        slot = intent.parameters.get(key)
        if slot and slot.source != "missing" and slot.value is not None:
            parameters[key] = slot.value
        else:
            parameters[key] = spec.default

    # Infer asset class if missing
    asset_class = intent.asset_class.value
    if not asset_class and intent.symbols.value:
        # Simple inference: if any symbol is BTC/ETH/SOL, it's crypto
        crypto_hints = {"BTC", "ETH", "SOL", "DOGE", "SHIB"}
        if any(s.upper() in crypto_hints for s in intent.symbols.value):
            asset_class = "crypto"
        else:
            asset_class = "equity"
    
    if not asset_class:
        asset_class = "equity"

    benchmark_symbol = intent.benchmark_symbol.value
    if not benchmark_symbol:
        benchmark_symbol = "BTC" if asset_class == "crypto" else "SPY"

    return {
        "template": template_str,
        "asset_class": asset_class,
        "symbols": intent.symbols.value or [],
        "timeframe": intent.timeframe.value or "1D",
        "start_date": intent.start_date.value,
        "end_date": intent.end_date.value,
        "side": "long",
        "starting_capital": intent.starting_capital.value or 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_symbol,
        "parameters": parameters,
    }


def _default_onboarding_prompt(language: str | None) -> str:
    if _resolve_language(language) == "es-419":
        return (
            "¿Cuál es tu objetivo principal ahora? No te preocupes, "
            "podrás cambiarlo después en Settings."
        )
    return (
        "What is your current primary goal? Don't worry, "
        "you can change it later in Settings."
    )


def _default_follow_up_for_goal(goal: str, language: str | None) -> str:
    normalized = _resolve_language(language)
    if normalized == "es-419":
        mapping = {
            "learn_basics": "Perfecto. Te ayudaré con ideas simples para empezar. ¿Qué activo te interesa?",
            "test_stock_idea": "Perfecto. Cuéntame tu idea de acción y la probamos.",
            "build_passive_strategy": "Perfecto. Podemos empezar con una idea pasiva tipo DCA.",
            "explore_crypto": "Perfecto. Empecemos con una idea de cripto que quieras validar.",
            "surprise_me": "Genial. Te propondré una idea inicial guiada para comenzar.",
        }
    else:
        mapping = {
            "learn_basics": "Great. I'll keep this beginner-friendly. What asset are you curious about?",
            "test_stock_idea": "Great. Share the stock idea you want to test and I'll run it.",
            "build_passive_strategy": "Great. We can start with a passive DCA-style idea.",
            "explore_crypto": "Great. Let's start with a crypto idea you want to validate.",
            "surprise_me": "Great. I'll guide you with a starter idea to begin.",
        }
    return mapping.get(goal, mapping["surprise_me"])


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    normalized_language = _resolve_language(language)
    if normalized_language == "es-419":
        return (
            f"Probé la idea con {joined}. Usé una simulación long-only, de peso igual, "
            "sin comisiones ni deslizamiento para mantener la comparación clara."
        )
    return (
        f"I tested that idea with {joined}. I used a long-only, equal-weight simulation "
        "with no fees or slippage so the comparison stays easy to understand."
    )


def _build_model(model_name: str) -> ChatOpenRouter:
    return ChatOpenRouter(
        model=model_name,
        temperature=0,
    )


def _llm_extract_decision(
    *,
    message: str,
    language: str | None,
    primary_goal: str | None,
    model_name: str,
    history: list[dict[str, str]] | None = None,
) -> ChatOrchestrationDecision:
    prompt_language = _resolve_language(language)
    model = _build_model(model_name)
    structured = model.with_structured_output(ChatOrchestrationDecision)

    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus Alpha orchestration. "
                "Use the provided conversation history to resolve pronouns (e.g., 'it', 'them') "
                "or symbols mentioned in previous turns. "
                "Return only supported intents and templates. "
                "Supported templates: buy_the_dip, rsi_mean_reversion, moving_average_crossover, "
                "dca_accumulation, momentum_breakout, trend_follow. "
                "Never propose unsupported capabilities. "
                "In 'assistant_message', ALWAYS use standard Markdown vertical lists (e.g., '- **Item**: description') for strategy lists. "
                "Never use horizontal dot-separated lists. Use vertical lists with newlines between paragraphs for clarity. "
                f"User language: {prompt_language}. Primary goal: {primary_goal or 'unknown'}."
            ),
        }
    ]

    if history:
        # Pass up to last 6 messages for context
        messages.extend(history[-6:])

    messages.append({"role": "user", "content": message})

    decision = structured.invoke(messages)
    if decision.strategy_intent:
        # Re-build intent with history awareness
        # Note: decision.strategy_intent might be partially filled by LLM
        # We use it as an extraction source
        extraction = StrategyExtraction(
            template=decision.strategy_intent.template.value,
            asset_class=decision.strategy_intent.asset_class.value,
            symbols=decision.strategy_intent.symbols.value or [],
            timeframe=decision.strategy_intent.timeframe.value,
            start_date=decision.strategy_intent.start_date.value,
            end_date=decision.strategy_intent.end_date.value,
            benchmark_symbol=decision.strategy_intent.benchmark_symbol.value,
            starting_capital=decision.strategy_intent.starting_capital.value,
            parameters={k: v.value for k, v in decision.strategy_intent.parameters.items()}
        )
        decision.strategy_intent = build_strategy_intent(
            extraction, (history or []) + [{"role": "user", "content": message}]
        )
    return decision


def _fallback_run_decision(
    message: str,
    language: str | None,
    primary_goal: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> ChatOrchestrationDecision:
    extracted = StrategyExtraction.model_validate(_heuristic_extract(message))
    intent = build_strategy_intent(
        extracted, (history or []) + [{"role": "user", "content": message}]
    )

    # Merge with history
    if history:
        last_intent_dict = next(
            (m.get("strategy_intent") for m in reversed(history) if m.get("strategy_intent")),
            None
        )
        if last_intent_dict:
            try:
                last_intent = StrategyIntent(**last_intent_dict)
                intent = merge_intent(intent, last_intent)
            except Exception:
                pass

    # Assess readiness using the intent and history
    plan = plan_strategy_action(intent, language)

    if plan.action == "run_backtest":
        return ChatOrchestrationDecision(
            intent="run_backtest",
            assistant_message=assistant_copy_for_result(
                intent.symbols.value or [], language or "en"
            ),
            strategy_intent=intent,
            title_suggestion=None,
        )

    if plan.action == "ask_clarification":
        return ChatOrchestrationDecision(
            intent="education",
            assistant_message=plan.message
            or (
                "Cuéntame más sobre tu estrategia."
                if _resolve_language(language) == "es-419"
                else "Tell me more about your strategy."
            ),
            strategy_intent=intent,
            title_suggestion=None,
        )

    # Fallback for unsupported or general chat
    goal = primary_goal or "surprise_me"
    assistant_message = goal_follow_up_message(goal, language)
    return ChatOrchestrationDecision(
        intent="unsupported_request",
        assistant_message=assistant_message,
        strategy_intent=intent,
        title_suggestion=None,
    )


def orchestrate_chat_turn(
    *,
    message: str,
    language: str | None,
    onboarding_required: bool,
    primary_goal: str | None,
    history: list[dict[str, str]] | None = None,
) -> ChatOrchestrationDecision:
    if onboarding_required:
        return ChatOrchestrationDecision(
            intent="onboarding_prompt",
            assistant_message=_default_onboarding_prompt(language),
        )

    primary_model = os.getenv("AGENT_MODEL")
    fallback_model = os.getenv("AGENT_FALLBACK_MODEL")
    has_provider_config = bool(primary_model and os.getenv("OPENROUTER_API_KEY"))
    if not has_provider_config:
        return _fallback_run_decision(message, language, primary_goal)

    try:
        decision = _llm_extract_decision(
            message=message,
            language=language,
            primary_goal=primary_goal,
            model_name=primary_model,
            history=history,
        )

        # 1. Merge with history if LLM returned an intent
        if decision.strategy_intent and history:
            last_intent_dict = next(
                (m.get("strategy_intent") for m in reversed(history) if m.get("strategy_intent")),
                None
            )
            if last_intent_dict:
                try:
                    last_intent = StrategyIntent(**last_intent_dict)
                    decision.strategy_intent = merge_intent(
                        decision.strategy_intent, last_intent
                    )
                except Exception:
                    pass

        # 2. Policy Enforcement: override LLM if readiness gate fails
        if decision.strategy_intent:
            plan = plan_strategy_action(decision.strategy_intent, language)
            if plan.action == "ask_clarification":
                decision.intent = "education"
                decision.assistant_message = (
                    plan.message or decision.assistant_message
                )
            elif plan.action == "run_backtest" and decision.intent != "run_backtest":
                # LLM extracted enough but didn't decide to run? Force run if it's high confidence or if we want to be proactive
                decision.intent = "run_backtest"
                decision.assistant_message = assistant_copy_for_result(
                    decision.strategy_intent.symbols.value or [], language or "en"
                )

        # 3. Validation
        if (
            decision.strategy_intent
            and decision.strategy_intent.template.value
            and str(decision.strategy_intent.template.value) not in STRATEGY_CAPABILITIES
        ):
            return _fallback_run_decision(message, language, primary_goal, history)

        if (
            decision.strategy_intent
            and not decision.strategy_intent.symbols.value
            and decision.intent == "run_backtest"
        ):
            return _fallback_run_decision(message, language, primary_goal, history)

        return decision
    except Exception:
        if fallback_model:
            try:
                decision = _llm_extract_decision(
                    message=message,
                    language=language,
                    primary_goal=primary_goal,
                    model_name=fallback_model,
                    history=history,
                )

                # Merge and validate for fallback too
                if decision.strategy_intent and history:
                    last_intent_dict = next(
                        (m.get("strategy_intent") for m in reversed(history) if m.get("strategy_intent")),
                        None
                    )
                    if last_intent_dict:
                        try:
                            last_intent = StrategyIntent(**last_intent_dict)
                            decision.strategy_intent = merge_intent(
                                decision.strategy_intent, last_intent
                            )
                        except Exception:
                            pass

                if decision.strategy_intent:
                    readiness = decide_run_readiness(
                        intent=decision.strategy_intent,
                        history=history or [],
                        language=language,
                    )
                    if not readiness.ready_to_run:
                        decision.intent = "education"
                        decision.assistant_message = (
                            readiness.clarification_prompt or decision.assistant_message
                        )

                return decision
            except Exception:
                pass
        return _fallback_run_decision(message, language, primary_goal, history)


def extract_strategy_request(message: str) -> dict[str, Any]:
    return _heuristic_extract(message)


def suggest_entity_name(
    *,
    entity_type: Literal["conversation", "strategy", "collection"],
    context: str,
    language: str | None,
) -> str | None:
    primary_model = os.getenv("AGENT_MODEL")
    if not primary_model or not os.getenv("OPENROUTER_API_KEY"):
        return None

    try:
        model = _build_model(primary_model)
        structured = model.with_structured_output(NameSuggestion)
        resolved = _resolve_language(language)
        response = structured.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate a concise user-facing name for Argus Alpha. "
                        "Max 6 words. No punctuation-only output. "
                        f"Entity type: {entity_type}. Language: {resolved}."
                    ),
                },
                {"role": "user", "content": context},
            ]
        )
        candidate = response.name.strip()
        if not candidate:
            return None
        return candidate[:80]
    except Exception:
        return None


def parse_onboarding_goal(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    if message.startswith("__ONBOARDING_GOAL__:"):
        goal = message.removeprefix("__ONBOARDING_GOAL__:").strip()
        if goal in SUPPORTED_GOALS:
            return goal
    return None


def goal_follow_up_message(goal: str, language: str | None) -> str:
    return _default_follow_up_for_goal(goal, language)

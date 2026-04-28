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
    value: Any | None = None
    source: Literal["user_supplied", "history_inferred", "backend_default", "missing"]
    confidence: float = 1.0


class StrategyRunDraft(BaseModel):
    template: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    asset_class: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    symbols: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    timeframe: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    start_date: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    end_date: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    benchmark_symbol: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    starting_capital: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    dca_cadence: SlotValue = Field(
        default_factory=lambda: SlotValue(source="missing")
    )
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_extraction(fixed_dates: bool = False) -> StrategyExtraction:
        """Convert draft slots into a flat StrategyExtraction for the engine."""
        return StrategyExtraction(
            template=self.template.value,
            asset_class=self.asset_class.value or "equity",
            symbols=self.symbols.value or [],
            timeframe=self.timeframe.value,
            start_date=self.start_date.value,
            end_date=self.end_date.value,
            benchmark_symbol=self.benchmark_symbol.value,
            parameters=self.parameters,
        )


class StrategyExtraction(BaseModel):
    template: str | None = None
    asset_class: Literal["equity", "crypto"]
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
        "onboarding_prompt",
        "education",
        "unsupported_request",
    ]
    assistant_message: str
    strategy: StrategyExtraction | None = None
    strategy_draft: StrategyRunDraft | None = None
    title_suggestion: str | None = None


class NameSuggestion(BaseModel):
    name: str


def build_strategy_draft(
    extraction: StrategyExtraction, history: list[dict[str, str]] | None = None
) -> StrategyRunDraft:
    """Assess where each parameter came from to guide readiness decisions."""
    history = history or []
    
    def get_source(field_name: str, value: Any) -> Literal["user_supplied", "history_inferred", "backend_default", "missing"]:
        if not value:
            return "missing"
        
        # Check if the field was mentioned in the last user message
        # This is a heuristic; in a real graph, the LLM would tag provenance
        last_user_msg = next((m["content"].upper() for m in reversed(history) if m["role"] == "user"), "")
        
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
            # If not in last message but exists, it's inferred from history or default
            return "history_inferred"

        # DCA Cadence check
        if field_name == "dca_cadence":
            if any(kw in last_user_msg for kw in ["DAILY", "WEEKLY", "MONTHLY", "DIARIA", "SEMANAL", "MENSUAL"]):
                return "user_supplied"
            return "missing"

        return "backend_default"

    return StrategyRunDraft(
        template=SlotValue(value=extraction.template, source=get_source("template", extraction.template)),
        asset_class=SlotValue(value=extraction.asset_class, source="backend_default"),
        symbols=SlotValue(value=extraction.symbols, source=get_source("symbols", extraction.symbols)),
        timeframe=SlotValue(value=extraction.timeframe, source=get_source("timeframe", extraction.timeframe)),
        start_date=SlotValue(value=extraction.start_date, source=get_source("start_date", extraction.start_date)),
        end_date=SlotValue(value=extraction.end_date, source=get_source("end_date", extraction.end_date)),
        benchmark_symbol=SlotValue(value=extraction.benchmark_symbol, source="backend_default"),
        starting_capital=SlotValue(value=extraction.starting_capital, source="backend_default"),
        dca_cadence=SlotValue(
            value=(extraction.parameters or {}).get("dca_cadence") or "weekly",
            source=get_source("dca_cadence", (extraction.parameters or {}).get("dca_cadence"))
        ),
        parameters=extraction.parameters,
    )


@dataclass(frozen=True)
class StrategyReadiness:
    ready_to_run: bool
    missing_fields: list[str] = field(default_factory=list)
    clarification_prompt: str | None = None


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


def decide_run_readiness(
    draft: StrategyRunDraft, history: list[dict[str, str]], language: str | None = None
) -> StrategyReadiness:
    """Determine if we can run or if we need to ask more questions."""
    missing = []
    
    # Policy: Always require symbols and template from user or history
    if draft.symbols.source == "missing":
        missing.append("symbols")
    if draft.template.source == "missing":
        missing.append("template")
    
    # Policy: For DCA, require explicit cadence from user or history
    if draft.template.value == "dca_accumulation":
        if draft.dca_cadence.source == "missing":
            missing.append("dca_cadence")

    # Policy: If we asked for time/dates in the last 3 turns and still don't have them from user, mark as missing
    # This prevents silent defaulting when the user is in the middle of answering a time question.
    pending_time_question = any(
        m["role"] == "assistant" and 
        any(kw in m["content"].lower() for kw in ["timeframe", "temporal", "period", "fecha", "cuándo", "cuando"])
        for m in history[-3:]
    )
    
    # If we asked and user didn't provide in this turn (source == history_inferred or backend_default means it wasn't in last msg)
    if pending_time_question:
        if draft.timeframe.source in ("missing", "backend_default", "history_inferred") and \
           draft.start_date.source in ("missing", "backend_default", "history_inferred"):
            # Check if last user message says "default" or "da igual" or similar
            last_user_msg = next((m["content"].lower() for m in reversed(history) if m["role"] == "user"), "")
            if not any(kw in last_user_msg for kw in ["default", "por defecto", "da igual", "any", "standard"]):
                missing.append("time_preferences")

    if not missing:
        return StrategyReadiness(ready_to_run=True)

    # Build clarification prompt
    lang = _resolve_language(language)
    prompts = []
    if "symbols" in missing:
        prompts.append("¿Qué símbolos quieres probar?" if lang == "es-419" else "Which symbols do you want to test?")
    if "template" in missing:
        prompts.append("¿Qué estrategia quieres usar?" if lang == "es-419" else "Which strategy do you want to use?")
    if "time_preferences" in missing:
        prompts.append("¿En qué periodo o temporalidad?" if lang == "es-419" else "For what period or timeframe?")
    if "dca_cadence" in missing:
        prompts.append("¿Con qué frecuencia quieres comprar (diaria, semanal, mensual)?" if lang == "es-419" else "How often do you want to buy (daily, weekly, monthly)?")

    return StrategyReadiness(
        ready_to_run=False,
        missing_fields=missing,
        clarification_prompt=" ".join(prompts)
    )


def assess_strategy_readiness(
    *,
    extracted: StrategyExtraction,
    language: str | None,
) -> StrategyReadiness:
    """Deprecated: Use decide_run_readiness instead."""
    draft = build_strategy_draft(extracted, [])
    return decide_run_readiness(draft, [], language)


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
    if decision.strategy:
        decision.strategy_draft = build_strategy_draft(
            decision.strategy, (history or []) + [{"role": "user", "content": message}]
        )
    return decision


def _fallback_run_decision(
    message: str, language: str | None, primary_goal: str | None = None, history: list[dict[str, str]] | None = None
) -> ChatOrchestrationDecision:
    extraction = StrategyExtraction.model_validate(_heuristic_extract(message))
    draft = build_strategy_draft(extraction, (history or []) + [{"role": "user", "content": message}])
    
    # Assess readiness using the draft and history
    readiness = decide_run_readiness(draft=draft, history=history or [], language=language)

    if readiness.ready_to_run:
        return ChatOrchestrationDecision(
            intent="run_backtest",
            assistant_message=assistant_copy_for_result(extraction.symbols, language or "en"),
            strategy=extraction,
            strategy_draft=draft,
            title_suggestion=None,
        )

    # If no symbols were found even by heuristic, treat as unsupported/general chat
    if not extraction.symbols:
        goal = primary_goal or "surprise_me"
        assistant_message = goal_follow_up_message(goal, language)
        return ChatOrchestrationDecision(
            intent="unsupported_request",
            assistant_message=assistant_message,
            strategy=None,
            strategy_draft=draft,
            title_suggestion=None,
        )

    return ChatOrchestrationDecision(
        intent="education",
        assistant_message=readiness.clarification_prompt or ("Cuéntame más sobre tu estrategia." if _resolve_language(language) == "es-419" else "Tell me more about your strategy."),
        strategy=extraction,
        strategy_draft=draft,
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
            strategy=None,
            title_suggestion=None,
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
        
        # Policy Enforcement: override LLM if readiness gate fails
        if decision.strategy_draft:
            readiness = decide_run_readiness(
                draft=decision.strategy_draft, 
                history=history or [], 
                language=language
            )
            if not readiness.ready_to_run:
                decision.intent = "education"
                decision.assistant_message = readiness.clarification_prompt or decision.assistant_message
        
        if decision.strategy and decision.strategy.template not in SUPPORTED_TEMPLATES:
            return _fallback_run_decision(message, language, primary_goal, history)
        if decision.strategy and not decision.strategy.symbols:
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
                
                # Policy Enforcement: override fallback LLM if readiness gate fails
                if decision.strategy_draft:
                    readiness = decide_run_readiness(
                        draft=decision.strategy_draft, 
                        history=history or [], 
                        language=language
                    )
                    if not readiness.ready_to_run:
                        decision.intent = "education"
                        decision.assistant_message = readiness.clarification_prompt or decision.assistant_message
                
                if (
                    decision.strategy
                    and decision.strategy.template in SUPPORTED_TEMPLATES
                ):
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

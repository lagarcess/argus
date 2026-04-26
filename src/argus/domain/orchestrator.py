from __future__ import annotations

import os
import re
from typing import Any, Literal

from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

SUPPORTED_TEMPLATES = {
    "buy_the_dip",
    "rsi_mean_reversion",
    "moving_average_crossover",
    "dca_accumulation",
    "momentum_breakout",
    "trend_follow",
}
SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}
TEMPLATE_ALIASES: list[tuple[str, str]] = [
    ("rsi_mean_reversion", "rsi"),
    ("rsi_mean_reversion", "dip"),
    ("moving_average_crossover", "moving average"),
    ("dca_accumulation", "dca"),
    ("momentum_breakout", "momentum"),
    ("momentum_breakout", "breakout"),
    ("trend_follow", "trend"),
]
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


class StrategyExtraction(BaseModel):
    template: str
    asset_class: Literal["equity", "crypto"]
    symbols: list[str] = Field(default_factory=list)
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
    title_suggestion: str | None = None


class NameSuggestion(BaseModel):
    name: str


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
    template = "rsi_mean_reversion"
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
        "symbols": symbols[:5] or ["TSLA"],
        "parameters": {},
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
) -> ChatOrchestrationDecision:
    prompt_language = _resolve_language(language)
    model = _build_model(model_name)
    structured = model.with_structured_output(ChatOrchestrationDecision)
    return structured.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are Argus Alpha orchestration. "
                    "Return only supported intents and templates. "
                    "Supported templates: buy_the_dip, rsi_mean_reversion, moving_average_crossover, "
                    "dca_accumulation, momentum_breakout, trend_follow. "
                    "Never propose unsupported capabilities. "
                    f"User language: {prompt_language}. Primary goal: {primary_goal or 'unknown'}."
                ),
            },
            {"role": "user", "content": message},
        ]
    )


def _fallback_run_decision(
    message: str, language: str | None
) -> ChatOrchestrationDecision:
    strategy = StrategyExtraction.model_validate(_heuristic_extract(message))
    return ChatOrchestrationDecision(
        intent="run_backtest",
        assistant_message=assistant_copy_for_result(strategy.symbols, language or "en"),
        strategy=strategy,
        title_suggestion=None,
    )


def orchestrate_chat_turn(
    *,
    message: str,
    language: str | None,
    onboarding_required: bool,
    primary_goal: str | None,
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
        return _fallback_run_decision(message, language)

    try:
        decision = _llm_extract_decision(
            message=message,
            language=language,
            primary_goal=primary_goal,
            model_name=primary_model,
        )
        if decision.strategy and decision.strategy.template not in SUPPORTED_TEMPLATES:
            return _fallback_run_decision(message, language)
        if decision.strategy and not decision.strategy.symbols:
            return _fallback_run_decision(message, language)
        return decision
    except Exception:
        if fallback_model:
            try:
                decision = _llm_extract_decision(
                    message=message,
                    language=language,
                    primary_goal=primary_goal,
                    model_name=fallback_model,
                )
                if (
                    decision.strategy
                    and decision.strategy.template in SUPPORTED_TEMPLATES
                ):
                    return decision
            except Exception:
                pass
        return _fallback_run_decision(message, language)


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

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any, Literal

from langchain_openrouter import ChatOpenRouter
from loguru import logger
from pydantic import BaseModel, Field

from argus.domain.backtest_state_machine import BacktestParamsUpdate
from argus.domain.market_data.assets import resolve_asset as _resolve_market_asset
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

resolve_asset = _resolve_market_asset  # compatibility shim for legacy tests only

SUPPORTED_TEMPLATES = set(STRATEGY_CAPABILITIES.keys())
SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}
DEFAULT_CHAT_INTENT_MODEL = "google/gemini-2.0-flash-001"

NON_SYMBOLS = {
    "WHAT", "IF", "WHENEVER", "WHEN", "BOUGHT", "BUY", "DIPPED", "HARD",
    "THE", "AND", "FOR", "WITH", "STOCK", "CRYPTO", "I", "ME", "MY", "YOU",
    "HOW", "WOULD", "SIMPLE", "STRATEGY", "PERFORM", "ON", "RUN", "TEST",
    "TODAY", "YTD", "YEAR", "BACK", "FROM", "START", "END", "DATE",
    "DCA", "RSI", "MA",
}

COMMON_NAMES = {
    "TESLA": "TSLA",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "GOOGLE": "GOOG",
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
    goal = primary_goal if primary_goal in STARTER_PROMPTS else "surprise_me"
    return STARTER_PROMPTS[goal]

# --- Models ---

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
    title_suggestion: str | None = None

class NameSuggestion(BaseModel):
    name: str


ChatTurnIntentName = Literal[
    "guide",
    "setup",
    "confirm",
    "explain_result",
    "refine",
    "unsupported",
]
EducationalNeed = Literal[
    "beginner_confused",
    "concept_explanation",
    "metric_explanation",
    "strategy_help",
    "none",
]
GuideChoice = Literal["specific_stock", "compare_stocks", "basic_strategy"]
ConfirmationAction = Literal[
    "accept_and_run",
    "edit_parameters",
    "cancel_backtest",
    "none",
]
ResultAction = Literal[
    "explain_metrics",
    "compare_or_refine",
    "save_or_organize",
    "none",
]


class ChatTurnIntent(BaseModel):
    intent: ChatTurnIntentName = "guide"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    educational_need: EducationalNeed = "none"
    guide_choice: GuideChoice | None = None
    backtest_update: BacktestParamsUpdate = Field(default_factory=BacktestParamsUpdate)
    confirmation_action: ConfirmationAction = "none"
    result_action: ResultAction = "none"
    assistant_guidance_seed: str | None = None

# --- Helper Logic ---

def _resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"

def parse_onboarding_goal(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    if message.startswith("__ONBOARDING_GOAL__:"):
        goal = message.split(":", 1)[1]
        if goal in SUPPORTED_GOALS:
            return goal
    return None


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    is_es = _resolve_language(language) == "es-419"

    if is_es:
        return (
            f"Probé tu idea con {joined}. Usé una simulación long-only, de peso igual, "
            "sin comisiones ni deslizamiento para mantener la comparación clara.\n\n"
            "Siguiente paso: explicar resultados, probar otro periodo/simbolo/estrategia, o guardar la idea."
        )
    return (
        f"I tested your idea with {joined}. I used a long-only, equal-weight simulation "
        "with no fees or slippage so the comparison stays easy to understand.\n\n"
        "Next steps: explain the results, try a different period/symbol/strategy, or save and organize the idea."
    )

def _build_model(model_name: str) -> ChatOpenRouter:
    return ChatOpenRouter(model=model_name, temperature=0)

def result_review_message(
    intent: ChatTurnIntent,
    message: str,
    language: str | None,
    run_metrics: dict[str, Any] | None = None,
) -> str:
    is_es = _resolve_language(language) == "es-419"
    lower = message.lower()
    if intent.result_action == "save_or_organize":
        return (
            "Puedo ayudarte a guardar esta estrategia o ponerla en una coleccion. Por ahora, dime el nombre que quieres usar."
            if is_es
            else "I can help you save this strategy or organize it into a collection. For now, tell me the name you want to use."
        )

    # Data-aware path: if we have actual metrics, explain from real data
    if run_metrics:
        return _build_data_aware_explanation(message, run_metrics, is_es)

    if any(kw in lower for kw in (
        "drawdown", "caida", "caída",
    )) or intent.educational_need == "metric_explanation":
        return (
            "Drawdown es la caida mas grande desde un pico hasta un valle durante la simulacion. Ayuda a entender cuanto dolor habria soportado la idea antes de recuperarse."
            if is_es
            else "Drawdown is the largest peak-to-trough drop during the simulation. It helps show how much pain the idea would have taken before recovering."
        )
    return (
        "Puedo explicar el rendimiento, el drawdown, la volatilidad o si los supuestos hacen que el resultado sea confiable."
        if is_es
        else "I can explain return, drawdown, volatility, or whether the assumptions make the result trustworthy."
    )


def refine_message(intent: ChatTurnIntent, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    update = intent.backtest_update
    if intent.result_action == "save_or_organize":
        return (
            "Puedo ayudarte a guardar esta estrategia o ponerla en una coleccion. Por ahora, dime el nombre que quieres usar."
            if is_es
            else "I can help you save this strategy or organize it into a collection. For now, tell me the name you want to use."
        )
    if update.symbols:
        joined = ", ".join(update.symbols)
        return (
            f"Perfecto. Probemos la misma idea con {joined}. Confirmare los parametros antes de correrla."
            if is_es
            else f"Good. We can try the same idea with {joined}. I will confirm the parameters before running it."
        )
    return (
        "Podemos refinar cambiando simbolo, periodo o estrategia. Que quieres ajustar?"
        if is_es
        else "We can refine by changing the symbol, period, or strategy. What do you want to adjust?"
    )


def setup_guidance_message(language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    return (
        "Si. Podemos probar una estrategia sin arriesgar dinero. Para empezar, elige una: comprar y mantener, comprar en caidas, RSI mean reversion o DCA."
        if is_es
        else "Yes. We can test a strategy without risking real money. To start, pick one: buy and hold, buy the dip, RSI mean reversion, or DCA."
    )


def _build_data_aware_explanation(
    message: str,
    run_metrics: dict[str, Any],
    is_es: bool,
) -> str:
    """Build an explanation grounded in the actual backtest metrics."""
    agg = run_metrics.get("aggregate", {})
    perf = agg.get("performance", {})
    risk = agg.get("risk", {})
    eff = agg.get("efficiency", {})
    config = run_metrics.get("config", {})

    total_return = perf.get("total_return_pct", "N/A")
    benchmark_return = perf.get("benchmark_return_pct", "N/A")
    delta = perf.get("delta_vs_benchmark_pct", "N/A")
    max_dd = risk.get("max_drawdown_pct", "N/A")
    volatility = risk.get("volatility_pct", "N/A")
    win_rate = eff.get("win_rate", "N/A")
    sharpe = eff.get("sharpe_ratio", "N/A")
    profit = perf.get("profit", "N/A")
    trades = eff.get("total_trades", "N/A")
    template = config.get("template", "unknown").replace("_", " ")
    symbols = ", ".join(config.get("symbols", []))
    benchmark = config.get("benchmark_symbol", "SPY")
    capital = config.get("starting_capital", 10000)

    # Try LLM-powered explanation if available
    if os.getenv("OPENROUTER_API_KEY"):
        try:
            return _llm_result_explanation(message, run_metrics, is_es)
        except Exception as exc:
            logger.warning("LLM result explanation failed, using structured fallback", error=str(exc))

    # Structured fallback: build a summary from real numbers
    if is_es:
        return (
            f"Tu estrategia de {template} con {symbols} tuvo un retorno total de {total_return}% "
            f"(vs {benchmark_return}% del benchmark {benchmark}, una diferencia de {delta}%). "
            f"La máxima caída fue {max_dd}%, la volatilidad {volatility}%, "
            f"y el ratio de Sharpe fue {sharpe}. "
            f"Capital inicial: ${capital:,.0f}, ganancia: ${profit}. "
            f"Total de operaciones: {trades}, tasa de acierto: {_fmt_pct(win_rate)}.\n\n"
            "¿Quieres que explique alguna métrica en detalle, o prefieres probar otra idea?"
        )
    return (
        f"Your {template} strategy on {symbols} returned {total_return}% total "
        f"(vs {benchmark_return}% for {benchmark}, a delta of {delta}%). "
        f"Max drawdown was {max_dd}%, volatility {volatility}%, "
        f"and Sharpe ratio was {sharpe}. "
        f"Starting capital: ${capital:,.0f}, profit: ${profit}. "
        f"Total trades: {trades}, win rate: {_fmt_pct(win_rate)}.\n\n"
        "Want me to explain any metric in detail, or try a different idea?"
    )


def _fmt_pct(value: Any) -> str:
    """Format a 0-1 float as percentage, or pass through if already formatted."""
    try:
        v = float(value)
        if v <= 1.0:
            return f"{v * 100:.1f}%"
        return f"{v:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _llm_result_explanation(
    message: str,
    run_metrics: dict[str, Any],
    is_es: bool,
) -> str:
    """Use the LLM to answer the user's question grounded in actual metrics."""
    agg = run_metrics.get("aggregate", {})
    config = run_metrics.get("config", {})
    model = _build_model(os.getenv("AGENT_MODEL") or DEFAULT_CHAT_INTENT_MODEL)
    lang_label = "Spanish" if is_es else "English"

    system_prompt = (
        "You are Argus, an AI investing idea validation assistant. "
        "The user just ran a backtest and is asking about the results. "
        "You have the ACTUAL metrics below. Answer ONLY from this data. "
        "NEVER say the simulation failed — it completed successfully. "
        "NEVER invent numbers. If the user asks about a metric not listed, say so. "
        f"Respond in {lang_label}. Keep the response concise (3-5 sentences). "
        "Use plain language a beginner can understand.\n\n"
        f"BACKTEST RESULTS:\n"
        f"Template: {config.get('template', 'unknown')}\n"
        f"Symbols: {', '.join(config.get('symbols', []))}\n"
        f"Period: {config.get('start_date', '?')} to {config.get('end_date', '?')}\n"
        f"Starting capital: ${config.get('starting_capital', 10000):,.0f}\n"
        f"Benchmark: {config.get('benchmark_symbol', 'SPY')}\n"
        f"Performance: {agg.get('performance', {})}\n"
        f"Risk: {agg.get('risk', {})}\n"
        f"Efficiency: {agg.get('efficiency', {})}\n"
    )

    response = model.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ])
    return str(response.content).strip()


def assistant_message_for_chat_turn(
    intent: ChatTurnIntent,
    message: str,
    language: str | None,
    run_metrics: dict[str, Any] | None = None,
) -> str:
    if intent.intent == "guide":
        if intent.educational_need == "concept_explanation":
            return education_assistant_message(message, language)
        return guided_beginner_message(intent, language)
    if intent.intent == "setup":
        return setup_guidance_message(language)
    if intent.intent == "explain_result":
        return result_review_message(intent, message, language, run_metrics=run_metrics)
    if intent.intent == "refine":
        return refine_message(intent, language)
    if intent.intent == "unsupported":
        return (
            "I can help with educational backtests for supported stock or crypto ideas, but I can't trade real money or give personalized financial advice."
        )
    return neutral_assistant_message(language)

# --- Core API ---



def normalize_backtest_update(update: BacktestParamsUpdate, pending_template: str | None = None) -> BacktestParamsUpdate:
    """Canonicalizes localized values in a BacktestParamsUpdate."""
    from argus.domain.slot_normalizer import normalize_template_name, normalize_parameter_value
    
    # 1. Template
    if update.template:
        update.template = normalize_template_name(update.template)
        
    # 2. Parameters
    template_key = update.template or pending_template
    if template_key and update.parameters:
        normalized = {}
        for key, val in update.parameters.items():
            normalized[key] = normalize_parameter_value(template_key, key, val)
        update.parameters = normalized
        
    return update



def classify_chat_turn_intent(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    language: str | None = None,
    primary_goal: str | None = None,
    onboarding_stage: str | None = None,
    pending_backtest_state: dict[str, Any] | None = None,
    model_name: str = DEFAULT_CHAT_INTENT_MODEL,
) -> ChatTurnIntent:
    if not os.getenv("OPENROUTER_API_KEY"):
        return ChatTurnIntent(
            intent="guide",
            confidence=0.0,
            educational_need="beginner_confused",
            assistant_guidance_seed="intent_unavailable",
        )

    try:
        model = _build_model(model_name)
        structured = model.with_structured_output(ChatTurnIntent)
        resolved = _resolve_language(language)
        response = structured.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Classify the latest Argus chat turn and extract only explicit backtest fields. "
                        "Return one JSON object matching the schema. Intent must be one of guide, "
                        "setup, confirm, explain_result, refine, unsupported. "
                        "Never execute a backtest. Never infer missing fields or defaults. "
                        "Use confirmation_action only when the user explicitly accepts, edits, or cancels a pending confirmation. "
                        "Use result_action only after a completed result exists. "
                        "CRITICAL: If 'latest_run_id' is present in the pending backtest state, "
                        "a backtest HAS completed successfully. If the user asks about results, "
                        "performance, metrics, returns, drawdown, or explanation, classify as "
                        "'explain_result'. NEVER say the simulation failed when latest_run_id exists. "
                        "CRITICAL: If conversation_mode is 'result_review', we are in post-result context. "
                        "Questions about the strategy, numbers, or outcomes are 'explain_result'. "
                        f"Language: {resolved}. Primary goal: {primary_goal or 'unknown'}. "
                        f"Onboarding stage: {onboarding_stage or 'unknown'}. "
                        f"Pending backtest state: {pending_backtest_state or {}}. "
                    ),
                },
                *[
                    {
                        "role": str(item.get("role", "user")),
                        "content": str(item.get("content", "")),
                    }
                    for item in (history or [])[-5:]
                ],
                {"role": "user", "content": message},
            ]
        )
        if isinstance(response, ChatTurnIntent):
            # Task 3: Normalize the extracted update
            pending_template = None
            if pending_backtest_state and "params" in pending_backtest_state:
                pending_template = pending_backtest_state["params"].get("template")
                
            response.backtest_update = normalize_backtest_update(
                response.backtest_update, 
                pending_template=pending_template
            )

            logger.info(
                "Chat turn intent classified",
                intent_source="llm",
                intent=response.intent,
                confidence=response.confidence,
                has_update=response.backtest_update.has_updates(),
            )
            return response


    except Exception as exc:
        logger.warning(
            "Chat turn intent classification failed",
            intent_source="unavailable",
            error=str(exc),
        )

    return ChatTurnIntent(
        intent="guide",
        confidence=0.0,
        educational_need="beginner_confused",
        assistant_guidance_seed="intent_unavailable",
    )


def guided_beginner_message(intent: ChatTurnIntent, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    if intent.guide_choice == "specific_stock":
        return (
            "Bien. ¿Qué acción quieres probar? Podemos ver su rendimiento histórico."
            if is_es
            else "Nice. Which stock do you want to test? We can look at its historical performance."
        )
    if intent.guide_choice == "compare_stocks":
        return (
            "Bien. Dime dos o tres acciones y comparamos cuál ha rendido mejor."
            if is_es
            else "Nice. Tell me two or three stocks and we'll compare which one performed better."
        )
    if intent.guide_choice == "basic_strategy":
        return (
            "Bien. Podemos probar algo simple como DCA (comprar un poco cada mes) o Buy the Dip."
            if is_es
            else "Nice. We can try something simple like DCA (buying a bit every month) or Buy the Dip."
        )

    if intent.educational_need == "beginner_confused":
        return (
            "No hay problema. Busquemos una idea simple para probar. ¿Una acción que conozcas?"
            if is_es
            else "No problem. Let's find a simple idea to test. A specific stock you know?"
        )
    if intent.educational_need == "strategy_help":
        return (
            "No hay problema. Busquemos una idea simple para probar. ¿Qué tal DCA o Buy the Dip?"
            if is_es
            else "No problem. Let's find a simple idea to test. How about Buy and Hold or Buy the Dip?"
        )

    return (
        "Hola. Soy Argus, tu asistente de validación de ideas. ¿Quieres probar una acción específica, comparar varias, o ver una estrategia simple como Buy the Dip?"
        if is_es
        else "Hi. I'm Argus, your idea validation assistant. Want to test a specific stock, compare a few, or see a simple strategy like Buy the Dip?"
    )


def education_assistant_message(message: str, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    if "momentum" in message.lower():
        return (
            "Momentum looks for strength in a stock's price trend. I can help you test it."
            if not is_es
            else "El momentum busca fuerza en la tendencia del precio. Puedo ayudarte a probarlo."
        )
    return (
        "I can help you learn about investing ideas by testing them. What would you like to know?"
        if not is_es
        else "Puedo ayudarte a aprender sobre ideas de inversión probándolas. ¿Qué te gustaría saber?"
    )


def setup_guidance_message(language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    return (
        "I've set up the basics. Want to test a strategy like Buy and Hold or RSI?"
        if not is_es
        else "He configurado lo básico. ¿Quieres probar una estrategia como Comprar y Mantener o RSI?"
    )


def result_review_message(intent: ChatTurnIntent, message: str, language: str | None, run_metrics: dict[str, Any] | None = None) -> str:
    is_es = _resolve_language(language) == "es-419"
    if run_metrics:
        return (
            "Based on the results, here's what happened. What else should we check?"
            if not is_es
            else "Basado en los resultados, esto es lo que pasó. ¿Qué más deberíamos revisar?"
        )
    return (
        "Here are the metrics from your simulation. What do you think?"
        if not is_es
        else "Aquí están las métricas de tu simulación. ¿Qué opinas?"
    )


def refine_message(intent: ChatTurnIntent, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    return (
        "I've updated the parameters. Ready to run the new simulation?"
        if not is_es
        else "He actualizado los parámetros. ¿Listo para correr la nueva simulación?"
    )


def neutral_assistant_message(language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    return (
        "I'm here to help you validate investing ideas. What's on your mind?"
        if not is_es
        else "Estoy aquí para ayudarte a validar ideas de inversión. ¿Qué tienes en mente?"
    )


def suggest_entity_name(
    *,
    entity_type: Literal["conversation", "strategy", "collection"],
    context: str,
    language: str | None,
) -> str | None:
    primary_model = os.getenv("AGENT_MODEL") or "google/gemini-2.0-flash-001"
    if not os.getenv("OPENROUTER_API_KEY"):
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
        return candidate if candidate else None
    except Exception:
        return None

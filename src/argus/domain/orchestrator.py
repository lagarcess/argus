from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.domain.backtest_state_machine import BacktestParamsUpdate
from argus.domain.market_data.assets import resolve_asset as _resolve_market_asset
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.llm.openrouter import (
    build_openrouter_model,
    log_openrouter_failure,
    resolve_openrouter_model,
)

resolve_asset = _resolve_market_asset  # compatibility shim for legacy tests only

SUPPORTED_TEMPLATES = set(STRATEGY_CAPABILITIES.keys())
SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}

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
        "Explain a market term simply",
        "What does buying every month mean?",
        "How do I test an idea?",
    ],
    "test_stock_idea": [
        "Buy Apple after big drops",
        "Hold Tesla for a year",
        "Compare Nvidia with Apple",
        "Test Microsoft when it starts rising",
    ],
    "build_passive_strategy": [
        "Buy SPY every month",
        "Compare a fund with a stock",
        "Test a simple long-term idea",
        "Start with a low-maintenance idea",
    ],
    "explore_crypto": [
        "Hold Bitcoin for a year",
        "Compare Ethereum and Bitcoin",
        "Buy Bitcoin after big drops",
        "Buy Bitcoin every month",
    ],
    "surprise_me": [
        "Show me a simple first idea",
        "Test a familiar stock",
        "Compare two familiar assets",
        "Explain a result like I am new",
    ],
}

def get_starter_prompts(primary_goal: str | None) -> list[str]:
    goal = primary_goal if primary_goal in STARTER_PROMPTS else "surprise_me"
    return STARTER_PROMPTS[goal]

# --- Models ---

ChatTurnIntentName = Literal[
    "small_talk",
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
    assistant_response: str = Field(..., description="Conversational message from Argus. Use this to be helpful, data-obsessed, and natural.")
    intent: ChatTurnIntentName = "guide"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    educational_need: EducationalNeed = "none"
    guide_choice: GuideChoice | None = None
    backtest_update: BacktestParamsUpdate = Field(default_factory=BacktestParamsUpdate)
    confirmation_action: ConfirmationAction = "none"
    result_action: ResultAction = "none"

class NameSuggestion(BaseModel):
    name: str

# --- Helper Logic ---

def _resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"

def build_capability_prompt() -> str:
    """Generates a text summary of all supported strategies for the LLM."""
    from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
    lines = ["SUPPORTED STRATEGIES:"]
    for cap in STRATEGY_CAPABILITIES.values():
        params = []
        for p in cap.parameters.values():
            params.append(f"{p.key} ({', '.join(p.allowed_values or [])})")
        param_str = f" Params: {', '.join(params)}" if params else ""
        lines.append(f"- {cap.display_name} (template: {cap.template}). {param_str}")
    return "\n".join(lines)

def parse_onboarding_goal(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    if message.startswith("__ONBOARDING_GOAL__:"):
        goal = message.split(":", 1)[1]
        if goal in SUPPORTED_GOALS:
            return goal
    return None


def assistant_message_for_chat_turn(
    intent: ChatTurnIntent,
    message: str,
    language: str | None,
    run_metrics: dict[str, Any] | None = None,
) -> str:
    # 100% of the message now comes from the AI.
    if intent.assistant_response:
        return intent.assistant_response

    is_es = _resolve_language(language) == "es-419"
    return (
        "I'm here to help you validate your investing ideas with real historical data. What's on your mind?"
        if not is_es
        else "Estoy aquí para ayudarte a validar tus ideas de inversión con datos históricos reales. ¿Qué tienes en mente?"
    )

# --- Core API ---

def normalize_backtest_update(update: BacktestParamsUpdate, pending_template: str | None = None) -> BacktestParamsUpdate:
    """Canonicalizes localized values in a BacktestParamsUpdate."""
    from argus.domain.slot_normalizer import (
        normalize_parameter_value,
        normalize_template_name,
    )

    if update.template:
        update.template = normalize_template_name(update.template)

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
    model_name: str | None = None,
) -> ChatTurnIntent:
    is_es = _resolve_language(language) == "es-419"
    # Respect the AGENT_MODEL from env
    resolved_model = resolve_openrouter_model(model_name)
    model = build_openrouter_model("chat_composer", model_name=resolved_model)

    if model is None:
        return ChatTurnIntent(
            intent="guide",
            assistant_response="I'm here to help you validate ideas, but I'm in offline mode right now!" if not is_es else "¡Estoy aquí para ayudarte, pero estoy en modo offline ahora mismo!"
        )

    try:
        # We use a combined prompt to get BOTH the soulful response and the intent.
        # But we make it less likely to crash by providing a clear fallback for the response.
        structured = model.with_structured_output(ChatTurnIntent)
        resolved_lang = _resolve_language(language)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are ARGUS, a Senior Quantitative Analyst. You talk like a technical peer, not a bot. "
                    "Be enthusiastic, technical, and data-obsessed. Avoid 'Assistant-ese' (e.g., 'Great question!', 'I'm here to help!'). "
                    "If the user greets you, be punchy and human. No emojis. "
                    "Avoid rigid tables. Talk about strategies (DCA, RSI, Momentum) in flowing text. "
                    "\n\n"
                    f"{build_capability_prompt()}\n\n"
                    "CORE INSTRUCTIONS:\n"
                    "1. 'assistant_response' MUST be a natural, conversational message. "
                    "2. Determine the 'intent' (small_talk, guide, setup, confirm, explain_result, refine, unsupported). "
                    "3. If a backtest is ready to be run, summarize it enthusiastically. "
                    f"User language: {resolved_lang}."
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

        response = structured.invoke(messages)
        if isinstance(response, ChatTurnIntent):
            # BREAK THE LOOP: If the user says "yes/si/go" and we are in a pending state, force confirmation.
            lower_msg = message.lower().strip()
            is_confirming = any(w in lower_msg for w in ["yes", "si", "ejecuta", "run", "go", "confirm", "vale", "dale"])

            if is_confirming and response.intent in ["guide", "setup", "small_talk"]:
                # If the model missed it, but it looks like a confirmation, we nudge it.
                response.intent = "confirm"
                response.confirmation_action = "accept_and_run"

            pending_template = None
            if pending_backtest_state and "params" in pending_backtest_state:
                pending_template = pending_backtest_state["params"].get("template")

            response.backtest_update = normalize_backtest_update(
                response.backtest_update,
                pending_template=pending_template
            )
            return response

    except Exception as exc:
        log_openrouter_failure(
            task="chat_composer",
            model_name=resolved_model,
            exc=exc,
            message="Classification failed",
        )
        # Soulful fallback that doesn't feel like a template
        return ChatTurnIntent(
            intent="guide",
            confidence=0.0,
            educational_need="beginner_confused",
            assistant_response="I'm sorry, I'm having a bit of trouble processing that. Could you try rephrasing your idea for me?" if not is_es else "Lo siento, ¡me está costando procesar eso! ¿Podrías intentar reformular tu idea?",
        )

def suggest_entity_name(
    *,
    entity_type: Literal["conversation", "strategy", "collection"],
    context: str,
    language: str | None,
) -> str | None:
    primary_model = resolve_openrouter_model()
    model = build_openrouter_model("name_suggestion", model_name=primary_model)
    if model is None:
        return None

    try:
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
    except Exception as exc:
        log_openrouter_failure(
            task="name_suggestion",
            model_name=primary_model,
            exc=exc,
            message="Name suggestion failed",
        )
        return None

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any, Literal

from langchain_openrouter import ChatOpenRouter
from loguru import logger
from pydantic import BaseModel, Field

from argus.domain.backtest_state_machine import BacktestParamsUpdate
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

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

class ExtractedSlot(BaseModel):
    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str | None = None

class StrategyIntentExtraction(BaseModel):
    wants_backtest: bool = False
    wants_education: bool = False
    template: ExtractedSlot = Field(default_factory=ExtractedSlot)
    symbols: ExtractedSlot = Field(default_factory=ExtractedSlot)
    asset_class: ExtractedSlot = Field(default_factory=ExtractedSlot)
    timeframe: ExtractedSlot = Field(default_factory=ExtractedSlot)
    start_date: ExtractedSlot = Field(default_factory=ExtractedSlot)
    end_date: ExtractedSlot = Field(default_factory=ExtractedSlot)
    starting_capital: ExtractedSlot = Field(default_factory=ExtractedSlot)
    parameters: dict[str, ExtractedSlot] = Field(default_factory=dict)
    user_confirmed_defaults: bool = False

class SlotValue(BaseModel):
    value: Any = None
    source: Literal["user_supplied", "history_inferred", "backend_default", "missing"]
    confidence: float = 0.0
    evidence: str | None = None

class StrategyDraft(BaseModel):
    template: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    symbols: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    asset_class: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    timeframe: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    start_date: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    end_date: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    starting_capital: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    side: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    allocation_method: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    benchmark_symbol: SlotValue = Field(default_factory=lambda: SlotValue(source="missing"))
    parameters: dict[str, SlotValue] = Field(default_factory=dict)

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
    strategy_draft: StrategyDraft | None = None
    title_suggestion: str | None = None

class StrategyPlanDecision(BaseModel):
    action: Literal["ask_clarification", "run_backtest", "unsupported"]
    missing_fields: list[str] = Field(default_factory=list)
    message: str | None = None

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

def slot_from_extraction(slot: ExtractedSlot) -> SlotValue:
    if slot.value is None or slot.confidence < 0.55:
        return SlotValue(source="missing")
    return SlotValue(
        value=slot.value,
        source="user_supplied",
        confidence=slot.confidence,
        evidence=slot.evidence,
    )

def _slot(value: Any, evidence: str, confidence: float = 0.95) -> ExtractedSlot:
    return ExtractedSlot(value=value, confidence=confidence, evidence=evidence)

def _set_if_empty(extraction: StrategyIntentExtraction, field_name: str, slot: ExtractedSlot) -> None:
    current = getattr(extraction, field_name)
    if current.value is None or current.confidence <= slot.confidence:
        setattr(extraction, field_name, slot)

def _merge_extraction(base: StrategyIntentExtraction, overlay: StrategyIntentExtraction) -> StrategyIntentExtraction:
    merged = base.model_copy(deep=True)
    merged.wants_backtest = base.wants_backtest or overlay.wants_backtest
    merged.wants_education = base.wants_education or overlay.wants_education
    merged.user_confirmed_defaults = base.user_confirmed_defaults or overlay.user_confirmed_defaults
    for field_name in (
        "template",
        "symbols",
        "asset_class",
        "timeframe",
        "start_date",
        "end_date",
        "starting_capital",
    ):
        overlay_slot = getattr(overlay, field_name)
        if overlay_slot.value is not None and overlay_slot.confidence >= 0.55:
            _set_if_empty(merged, field_name, overlay_slot)
    for key, overlay_slot in overlay.parameters.items():
        current = merged.parameters.get(key)
        if current is None or current.value is None or current.confidence <= overlay_slot.confidence:
            merged.parameters[key] = overlay_slot
    return merged

def _extract_history_deterministic(history: list[dict[str, Any]] | None) -> StrategyIntentExtraction:
    merged = StrategyIntentExtraction()
    if not history:
        return merged
    for m in history:
        if m.get("role") == "user" and m.get("content"):
            merged = _merge_extraction(merged, _extract_deterministic_intent(str(m["content"])))
    return merged

def _extract_deterministic_intent(text: str) -> StrategyIntentExtraction:
    extraction = StrategyIntentExtraction()
    if not text.strip():
        return extraction

    lower = text.lower()
    if re.search(r"\b(backtest|test|run|perform|simulate|probar|ejecutar|correr|simular)\b", lower):
        extraction.wants_backtest = True
    if re.search(r"\b(how|what is|explain|funciona|explica|aprend)\b", lower):
        extraction.wants_education = True

    for capability in STRATEGY_CAPABILITIES.values():
        aliases = [capability.template, capability.display_name, *capability.aliases]
        if any(re.search(rf"\b{re.escape(alias.lower())}\b", lower) for alias in aliases):
            extraction.template = _slot(capability.template, "deterministic_template")
            break

    symbols: list[str] = []
    for name, symbol in COMMON_NAMES.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", lower):
            symbols.append(symbol)
    for token in re.findall(r"\b[A-Z]{2,5}(?:[-/](?:USD|USDT))?\b", text):
        if token not in NON_SYMBOLS:
            symbols.append(token)
    normalized = normalize_symbols(symbols)
    if normalized:
        extraction.symbols = _slot(normalized, "deterministic_symbols")
        extraction.asset_class = _slot(infer_asset_class(normalized), "deterministic_asset_class", 0.85)

    cadence_patterns = {
        "daily": r"\b(daily|diario|diaria|diariamente|every day|cada dia|cada d[ií]a)\b",
        "weekly": r"\b(weekly|weeklu|semanal|semanalmente|every week|cada semana)\b",
        "monthly": r"\b(monthly|mensual|mensualmente|every month|cada mes)\b",
    }
    for cadence, pattern in cadence_patterns.items():
        if re.search(pattern, lower):
            extraction.parameters["dca_cadence"] = _slot(cadence, "deterministic_cadence")
            break

    capital_match = re.search(
        r"\b(?:capital(?:\s+of)?|start(?:ing)?(?:\s+with)?|empieza(?:\s+con)?|con)?\s*\$?\s*(\d+(?:[.,]\d+)?)\s*(k|mil|thousand)?\b",
        lower,
    )
    if capital_match and any(word in lower for word in ("capital", "start", "empieza", "10k", "mil", "thousand")):
        amount = float(capital_match.group(1).replace(",", "."))
        if capital_match.group(2) in {"k", "mil", "thousand"}:
            amount *= 1000
        extraction.starting_capital = _slot(amount, "deterministic_capital")

    today = date.today()
    if re.search(r"\b(one|1|exactly a)\s+year\b|\b1\s*a[nñ]o\b|\ba[nñ]o\s+hacia\s+atras\b", lower):
        extraction.start_date = _slot((today - timedelta(days=365)).isoformat(), "deterministic_one_year")
        extraction.end_date = _slot(today.isoformat(), "deterministic_one_year")
        extraction.timeframe = _slot("1D", "deterministic_daily_timeframe", 0.8)
    if "ytd" in lower:
        extraction.start_date = _slot(date(today.year, 1, 1).isoformat(), "deterministic_ytd")
        extraction.end_date = _slot(today.isoformat(), "deterministic_ytd")
        extraction.timeframe = _slot("1D", "deterministic_daily_timeframe", 0.8)
    if re.search(r"\btoday\b|\bhoy\b", lower) and extraction.end_date.value is None:
        extraction.end_date = _slot(today.isoformat(), "deterministic_today", 0.85)
    return extraction

def merge_slot(current: SlotValue, previous: SlotValue) -> SlotValue:
    if current.source != "missing":
        return current
    return previous

def merge_draft(previous: StrategyDraft | None, extraction: StrategyIntentExtraction) -> StrategyDraft:
    current = StrategyDraft(
        template=slot_from_extraction(extraction.template),
        symbols=slot_from_extraction(extraction.symbols),
        asset_class=slot_from_extraction(extraction.asset_class),
        timeframe=slot_from_extraction(extraction.timeframe),
        start_date=slot_from_extraction(extraction.start_date),
        end_date=slot_from_extraction(extraction.end_date),
        starting_capital=slot_from_extraction(extraction.starting_capital),
        parameters={k: slot_from_extraction(v) for k, v in extraction.parameters.items()},
    )

    if previous is None:
        return current

    merged_params = dict(previous.parameters)
    for key, value in current.parameters.items():
        if value.source != "missing":
            merged_params[key] = value

    return StrategyDraft(
        template=merge_slot(current.template, previous.template),
        symbols=merge_slot(current.symbols, previous.symbols),
        asset_class=merge_slot(current.asset_class, previous.asset_class),
        timeframe=merge_slot(current.timeframe, previous.timeframe),
        start_date=merge_slot(current.start_date, previous.start_date),
        end_date=merge_slot(current.end_date, previous.end_date),
        starting_capital=merge_slot(current.starting_capital, previous.starting_capital),
        parameters=merged_params,
    )

def canonical_template(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).lower()
    if raw in STRATEGY_CAPABILITIES:
        return raw
    for capability in STRATEGY_CAPABILITIES.values():
        if raw in [alias.lower() for alias in capability.aliases]:
            return capability.template
    return None

def infer_asset_class(symbols: list[str]) -> Literal["equity", "crypto"]:
    if not symbols:
        return "equity"
    crypto_symbols = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT"}
    for s in symbols:
        up = str(s).upper()
        if up in crypto_symbols or "/" in up or up.endswith("USD"):
            return "crypto"
    return "equity"

def normalize_symbols(raw_symbols: Any) -> list[str]:
    if not raw_symbols:
        return []
    if isinstance(raw_symbols, str):
        raw_symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]

    normalized = []
    if isinstance(raw_symbols, list):
        for s in raw_symbols:
            up = str(s).upper().strip()
            if up in COMMON_NAMES:
                normalized.append(COMMON_NAMES[up])
            elif up not in NON_SYMBOLS and len(up) <= 10:
                normalized.append(up)

    unique = []
    for r in normalized:
        if r not in unique:
            unique.append(r)
    return unique[:5]

def normalize_draft(draft: StrategyDraft) -> StrategyDraft:
    template = canonical_template(draft.template.value)
    if template:
        draft.template = SlotValue(
            value=template,
            source=draft.template.source,
            confidence=draft.template.confidence,
            evidence=draft.template.evidence,
        )

    symbols = normalize_symbols(draft.symbols.value or [])
    if symbols:
        draft.symbols = SlotValue(
            value=symbols,
            source=draft.symbols.source,
            confidence=draft.symbols.confidence,
            evidence=draft.symbols.evidence,
        )

    if draft.asset_class.source == "missing" and symbols:
        draft.asset_class = SlotValue(
            value=infer_asset_class(symbols),
            source="backend_default",
            confidence=1.0,
        )

    return draft

def plan_draft_action(draft: StrategyDraft, language: str) -> StrategyPlanDecision:
    is_es = _resolve_language(language) == "es-419"
    missing = []
    if draft.template.source == "missing":
        missing.append("template")
    if draft.symbols.source == "missing":
        missing.append("symbols")

    if not missing:
        # Check for missing required/clarify parameters
        capability = STRATEGY_CAPABILITIES.get(str(draft.template.value))
        if capability:
            for key, spec in capability.parameters.items():
                if spec.policy == "clarify_if_missing":
                    slot = draft.parameters.get(key)
                    if not slot or slot.source == "missing":
                        missing.append(key)
                        msg = (
                            f"Necesito un dato más: {spec.description}" if is_es
                            else f"I need one more thing: {spec.description}"
                        )
                        return StrategyPlanDecision(action="ask_clarification", missing_fields=[key], message=msg)

        return StrategyPlanDecision(action="run_backtest")

    if "template" in missing and "symbols" in missing:
        msg = (
            "Cuéntame, ¿qué estrategia quieres probar y con qué símbolos?"
            if is_es
            else "Tell me, what strategy do you want to test and with which symbols?"
        )
    elif "template" in missing:
        msg = (
            f"Tengo los símbolos {', '.join(draft.symbols.value or [])}. ¿Qué estrategia quieres aplicar?"
            if is_es
            else f"I have {', '.join(draft.symbols.value or [])}. What strategy should we apply?"
        )
    else:
        # Symbols missing
        capability = STRATEGY_CAPABILITIES.get(str(draft.template.value))
        name = capability.display_name if capability else str(draft.template.value)
        msg = (
            f"Probaré {name}. ¿Con qué símbolos quieres correrla?"
            if is_es
            else f"I'll test {name}. Which symbols should we use?"
        )

    return StrategyPlanDecision(action="ask_clarification", missing_fields=missing, message=msg)

def compile_backtest_payload(draft: StrategyDraft) -> dict[str, Any]:
    template = str(draft.template.value)
    symbols = draft.symbols.value or []
    asset_class = draft.asset_class.value or "equity"

    end_date = draft.end_date.value or date.today().isoformat()
    start_date = draft.start_date.value or (date.today() - timedelta(days=365)).isoformat()

    benchmark = "BTC" if asset_class == "crypto" else "SPY"

    params = {}
    capability = STRATEGY_CAPABILITIES.get(template)
    if capability:
        for key, spec in capability.parameters.items():
            slot = draft.parameters.get(key)
            if slot and slot.source != "missing":
                params[key] = slot.value
            else:
                params[key] = spec.default

    return {
        "template": template,
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": draft.timeframe.value or "1D",
        "start_date": start_date,
        "end_date": end_date,
        "side": "long",
        "starting_capital": draft.starting_capital.value or 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark,
        "parameters": params,
    }

def assistant_copy_for_result(symbols: list[str], language: str, draft: StrategyDraft | None = None) -> str:
    joined = ", ".join(symbols)
    is_es = _resolve_language(language) == "es-419"

    strategy_display = ""
    if draft and draft.template.value:
        cap = STRATEGY_CAPABILITIES.get(str(draft.template.value))
        if cap:
            strategy_display = f" {cap.display_name}"

    if is_es:
        return (
            f"Probé tu idea de{strategy_display} con {joined}. Usé una simulación long-only, de peso igual, "
            "sin comisiones ni deslizamiento para mantener la comparación clara.\n\n"
            "Siguiente paso: explicar resultados, probar otro periodo/simbolo/estrategia, o guardar la idea."
        )
    return (
        f"I tested your{strategy_display} idea with {joined}. I used a long-only, equal-weight simulation "
        "with no fees or slippage so the comparison stays easy to understand.\n\n"
        "Next steps: explain the results, try a different period/symbol/strategy, or save and organize the idea."
    )

def _build_model(model_name: str) -> ChatOpenRouter:
    return ChatOpenRouter(model=model_name, temperature=0)

def build_capability_prompt() -> str:
    lines = ["Argus Alpha can run these supported templates:"]
    for cap in STRATEGY_CAPABILITIES.values():
        lines.append(
            f"- {cap.template}: aliases={cap.aliases}; "
            f"assets={cap.supported_asset_classes}; "
            f"parameters={list(cap.parameters)}"
        )
    return "\n".join(lines)

def goal_follow_up_message(goal: str, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    if is_es:
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


def neutral_assistant_message(language: str | None) -> str:
    if _resolve_language(language) == "es-419":
        return "Hola. Cuéntame una idea de inversión o trading que quieras explorar."
    return "Hi. Tell me what investing idea you want to explore."


def education_assistant_message(message: str, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    lower = message.lower()
    if "momentum" in lower:
        return (
            "Momentum busca activos que ya muestran fuerza y prueba si esa fuerza continúa."
            if is_es
            else "Momentum looks for strength that continues over time."
        )
    if "rsi" in lower:
        return (
            "RSI mide si un activo parece sobrecomprado o sobrevendido según sus movimientos recientes."
            if is_es
            else "RSI measures whether an asset looks overbought or oversold based on recent moves."
        )
    return (
        "Puedo explicarlo de forma simple o ayudarte a convertirlo en un backtest."
        if is_es
        else "I can explain it simply or help turn it into a backtest."
    )


def guided_beginner_message(intent: ChatTurnIntent, language: str | None) -> str:
    is_es = _resolve_language(language) == "es-419"
    if intent.assistant_guidance_seed == "intent_unavailable":
        return (
            "Ahora mismo no puedo leer bien tu intención. Puedo ayudarte a aprender un concepto, escoger una idea simple o probar una estrategia. ¿Qué quieres hacer primero?"
            if is_es
            else "I cannot reliably read your intent right now. I can help you learn a concept, pick a simple idea, or test a strategy. What do you want to do first?"
        )
    if intent.educational_need == "strategy_help":
        return (
            "Si. Puedes probar una estrategia simple sin arriesgar dinero. Empecemos con una: comprar y mantener, comprar en caidas o cruce de medias. Cual quieres probar?"
            if is_es
            else "Yes. You can test a simple strategy without risking real money. Start with one of these: buy and hold, buy the dip, or moving average crossover. Which one do you want to try?"
        )
    if intent.guide_choice == "specific_stock":
        return (
            "Perfecto. Elige una acción que conozcas, por ejemplo Apple, Tesla o Microsoft."
            if is_es
            else "Good. Pick one stock you recognize, for example Apple, Tesla, or Microsoft."
        )
    if intent.guide_choice == "compare_stocks":
        return (
            "Podemos comparar dos acciones conocidas. Un buen primer ejemplo es AAPL vs MSFT durante el último año. ¿Quieres probar eso?"
            if is_es
            else "We can compare two familiar tech stocks. A good first example is AAPL vs MSFT over the last year. Want to try that?"
        )
    if intent.guide_choice == "basic_strategy":
        return (
            "Podemos empezar simple: comprar y mantener, comprar en caídas o cruce de medias. ¿Cuál te interesa?"
            if is_es
            else "We can start simple: buy and hold, buy the dip, or moving average crossover. Which one sounds interesting?"
        )
    if intent.educational_need == "none":
        return (
            "Hola. Puedo ayudarte a aprender un concepto, escoger una idea simple o probar una estrategia. Que quieres hacer primero?"
            if is_es
            else "Hi. I can help you learn a market concept, pick a simple idea, or test a strategy. What do you want to do first?"
        )
    return (
        "No hay problema. Busquemos una idea simple para probar.\n\n"
        "1. Una acción específica que te interese, como Tesla o Apple\n"
        "2. Comparar dos acciones\n"
        "3. Probar una estrategia básica como comprar y mantener o cruce de medias\n\n"
        "Elige un número o dime qué te llama la atención."
        if is_es
        else "No problem. Let's find a simple idea to test.\n\n"
        "1. A specific stock you're curious about, like Tesla or Apple\n"
        "2. Comparing two stocks\n"
        "3. Testing a basic strategy like buy and hold or moving average crossover\n\n"
        "Pick a number or tell me what comes to mind."
    )


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

def _extract_strategy_intent(message: str, model_name: str, history: list[dict[str, Any]] | None = None) -> StrategyIntentExtraction:
    model = _build_model(model_name)
    structured = model.with_structured_output(StrategyIntentExtraction)

    system_prompt = (
        "You are a structured extraction engine for financial strategies. "
        "Your ONLY job is to output JSON matching the provided schema. "
        "DO NOT write a conversational response. DO NOT explain anything. "
        "Extract strategy type, symbols, and parameters from the user's input. "
        "Use the history for context if the user's latest message is short (e.g. just a symbol or a number). "
        "Confidence is 1.0 if explicitly stated, 0.5 if implied, 0.0 if missing. "
        f"{build_capability_prompt()}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # Add a few history items for context
    if history:
        for m in history[-5:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    messages.append({"role": "user", "content": message})

    try:
        res = structured.invoke(messages)
        if isinstance(res, StrategyIntentExtraction):
            return res
        return StrategyIntentExtraction()
    except Exception as e:
        logger.warning(f"Extraction failed: {e}")
        return StrategyIntentExtraction()


def _update_from_extraction(extraction: StrategyIntentExtraction) -> BacktestParamsUpdate:
    params: dict[str, Any] = {}
    if extraction.template.value is not None and extraction.template.confidence >= 0.55:
        params["template"] = extraction.template.value
    if extraction.symbols.value is not None and extraction.symbols.confidence >= 0.55:
        params["symbols"] = extraction.symbols.value
    if extraction.asset_class.value is not None and extraction.asset_class.confidence >= 0.55:
        params["asset_class"] = extraction.asset_class.value
    if extraction.timeframe.value is not None and extraction.timeframe.confidence >= 0.55:
        params["timeframe"] = extraction.timeframe.value
    if extraction.start_date.value is not None and extraction.start_date.confidence >= 0.55:
        params["start_date"] = extraction.start_date.value
    if extraction.end_date.value is not None and extraction.end_date.confidence >= 0.55:
        params["end_date"] = extraction.end_date.value
    if (
        extraction.starting_capital.value is not None
        and extraction.starting_capital.confidence >= 0.55
    ):
        params["starting_capital"] = extraction.starting_capital.value
    tool_params = {
        key: slot.value
        for key, slot in extraction.parameters.items()
        if slot.value is not None and slot.confidence >= 0.55
    }
    if tool_params:
        params["parameters"] = tool_params
    return BacktestParamsUpdate.model_validate(params)


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
        logger.warning("Chat turn intent provider unavailable", intent_source="unavailable")
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
                        f"{build_capability_prompt()}"
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


def final_decision_from_plan(
    *,
    plan: StrategyPlanDecision,
    draft: StrategyDraft,
    lang: str,
    primary_goal: str | None = None,
) -> ChatOrchestrationDecision:
    if plan.action == "run_backtest":
        return ChatOrchestrationDecision(
            intent="run_backtest",
            assistant_message=assistant_copy_for_result(draft.symbols.value or [], lang, draft),
            strategy_draft=draft,
        )

    if plan.action == "ask_clarification":
        return ChatOrchestrationDecision(
            intent="clarify",
            assistant_message=plan.message or "Tell me more.",
            strategy_draft=draft,
        )

    # Fallback/Unsupported
    return ChatOrchestrationDecision(
        intent="unsupported_request",
        assistant_message=goal_follow_up_message(primary_goal or "surprise_me", lang),
        strategy_draft=draft,
    )

def orchestrate_chat_turn(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    language: str | None = None,
    onboarding_required: bool = False,
    primary_goal: str | None = None,
    model_name: str = "google/gemini-2.0-flash-001",
) -> ChatOrchestrationDecision:
    lang = language or "en"
    history_len = len(history) if history else 0
    logger.info(f"Chat Turn started. Message: '{message[:50]}...' Lang: {lang}. History items: {history_len}")

    if onboarding_required:
        return ChatOrchestrationDecision(
            intent="onboarding_prompt",
            assistant_message=_default_onboarding_prompt(lang),
        )

    # 1. Extraction (History-aware). The deterministic layer is a guardrail:
    # live chat should not loop just because provider extraction drops prior slots.
    try:
        llm_extraction = _extract_strategy_intent(message, model_name, history)
    except TypeError:
        llm_extraction = _extract_strategy_intent(message, model_name)
    history_extraction = _extract_history_deterministic(history)
    current_extraction = _extract_deterministic_intent(message)
    extraction = _merge_extraction(history_extraction, llm_extraction)
    extraction = _merge_extraction(extraction, current_extraction)

    # 2. Rehydrate previous draft
    previous_draft = None
    if history:
        for m in reversed(history):
            if m.get("role") == "assistant" and m.get("metadata"):
                meta = m["metadata"]
                if "strategy_draft" in meta:
                    try:
                        previous_draft = StrategyDraft.model_validate(meta["strategy_draft"])
                        logger.info(f"Rehydrated draft: {previous_draft.template.value}")
                        break
                    except Exception as e:
                        logger.warning(f"Rehydration failed: {e}")

    if not previous_draft:
        logger.info("No previous draft found in history.")

    # 3. Merge and Normalize
    draft = merge_draft(previous_draft, extraction)
    draft = normalize_draft(draft)

    logger.info(f"Extracted: {extraction.model_dump_json(exclude_none=True)}")
    logger.info(f"Final merged draft: {draft.model_dump_json(exclude_none=True)}")

    has_active_draft = previous_draft is not None
    has_backtest_slots = any(
        slot.source != "missing"
        for slot in (
            draft.template,
            draft.symbols,
            draft.asset_class,
            draft.timeframe,
            draft.start_date,
            draft.end_date,
            draft.starting_capital,
        )
    ) or any(slot.source != "missing" for slot in draft.parameters.values())
    if not has_active_draft and extraction.wants_education and not extraction.wants_backtest:
        return ChatOrchestrationDecision(
            intent="education",
            assistant_message=education_assistant_message(message, lang),
        )
    if not has_active_draft and not extraction.wants_backtest and not has_backtest_slots:
        return ChatOrchestrationDecision(
            intent="answer",
            assistant_message=neutral_assistant_message(lang),
        )

    # 4. Plan Action
    plan = plan_draft_action(draft, lang)

    # 5. Final Decision
    return final_decision_from_plan(
        plan=plan,
        draft=draft,
        lang=lang,
        primary_goal=primary_goal,
    )

def _default_onboarding_prompt(language: str) -> str:
    if _resolve_language(language) == "es-419":
        return (
            "¿Cuál es tu objetivo principal ahora? No te preocupes, "
            "podrás cambiarlo después en Settings."
        )
    return (
        "What is your current primary goal? Don't worry, "
        "you can change it later in Settings."
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

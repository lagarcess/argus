from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal, cast

from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

from argus.domain.market_data import resolve_asset
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

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

def compile_backtest_payload(draft: StrategyDraft) -> dict[str, Any]:
    """
    Task 12: Payload Compiler.
    Flattens a StrategyDraft into a dict ready for the backtest engine.
    Applies registry defaults for missing fields.
    """
    template_id = draft.template.value
    # Registry lookup for defaults
    capability = STRATEGY_CAPABILITIES.get(template_id or "dca_accumulation")
    
    # Symbols normalization
    symbols = draft.symbols.value or []
    
    # Benchmarks
    asset_class = draft.asset_class.value or "equity"
    default_bench = "BTC" if asset_class == "crypto" else "SPY"
    
    # Parameters merge
    final_params = {}
    if capability:
        for p_id, p_info in capability.parameters.items():
            val = draft.parameters.get(p_id)
            if val and val.value is not None:
                final_params[p_id] = val.value
            else:
                final_params[p_id] = p_info.default

    return {
        "template": template_id,
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": draft.timeframe.value or "1D",
        "start_date": draft.start_date.value.isoformat() if hasattr(draft.start_date.value, "isoformat") else draft.start_date.value,
        "end_date": draft.end_date.value.isoformat() if hasattr(draft.end_date.value, "isoformat") else draft.end_date.value,
        "side": draft.side.value or "long",
        "starting_capital": draft.starting_capital.value or 10000,
        "allocation_method": draft.allocation_method.value or "equal_weight",
        "benchmark_symbol": draft.benchmark_symbol.value or default_bench,
        "parameters": final_params,
    }

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
            "sin comisiones ni deslizamiento para mantener la comparación clara."
        )
    return (
        f"I tested your{strategy_display} idea with {joined}. I used a long-only, equal-weight simulation "
        "with no fees or slippage so the comparison stays easy to understand."
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

    
def final_decision_from_plan(
    *,
    plan: OrchestrationPlan,
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
    from loguru import logger
    
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

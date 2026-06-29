"""Answer-composition helpers (non-LLM): capability/context/recovery answer support, packet grounding, fact packets.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.stages.interpret_types import (
    CapabilityQuestionFocus,
    ContextQuestionFocus,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import executable_strategy_type
from argus.context import ContextPacket
from argus.domain.indicators import EXECUTABLE_INDICATORS

_STANDALONE_CONTEXT_PACKET_TIMEOUT_SECONDS = 2.5


_SUPPORTED_STRATEGY_FAMILY_TERMS: tuple[str, ...] = (
    "buy and hold",
    "buy-and-hold",
    "hold",
    "recurring buys",
    "recurring buy",
    "dca",
    "dollar cost averaging",
    "indicator threshold",
    "indicator rules",
    "signal rules",
    "moving average",
    "macd",
    "bollinger band",
)


@dataclass(frozen=True)
class _LiveContextCuriosityFacts:
    content: str
    packet_symbols: tuple[str, ...] = ()


def _capability_answer_respects_contract(
    *,
    answer: str | None,
    focus: CapabilityQuestionFocus,
) -> bool:
    if not answer:
        return False
    if focus in {"supported_strategies", "general"} and (
        _answer_contradicts_supported_strategy_families(answer)
    ):
        return False
    if focus != "supported_indicators":
        return True
    return not _answer_contradicts_supported_indicators(answer)


def _answer_contradicts_supported_strategy_families(answer: str) -> bool:
    for sentence in _plain_sentences(answer):
        tokens = _plain_word_tokens(sentence)
        if not tokens:
            continue
        strategy_spans = _supported_strategy_family_token_spans(tokens)
        if not strategy_spans:
            continue
        negative_positions = _negative_support_claim_positions(tokens)
        for start, end in strategy_spans:
            if any(start - 3 <= position <= end + 6 for position in negative_positions):
                return True
    return False


def _answer_contradicts_supported_indicators(answer: str) -> bool:
    for sentence in _plain_sentences(answer):
        tokens = _plain_word_tokens(sentence)
        if not tokens:
            continue
        indicator_spans = _supported_indicator_token_spans(tokens)
        if not indicator_spans:
            continue
        negative_positions = _negative_support_claim_positions(tokens)
        for start, end in indicator_spans:
            if any(start - 3 <= position <= end + 6 for position in negative_positions):
                return True
    return False


def _supported_strategy_family_token_spans(tokens: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for term in _SUPPORTED_STRATEGY_FAMILY_TERMS:
        term_tokens = _plain_word_tokens(term)
        if not term_tokens:
            continue
        spans.extend(_token_sequence_spans(tokens, term_tokens))
    return spans


def _plain_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(str(text or "")):
        if char not in ".?!":
            continue
        sentence = text[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1
    trailing = text[start:].strip()
    if trailing:
        sentences.append(trailing)
    return sentences


def _plain_word_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in str(text or "").casefold():
        if char.isalnum():
            current.append(char)
            continue
        if char == "'":
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _supported_indicator_token_spans(tokens: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for spec in EXECUTABLE_INDICATORS.values():
        terms = (spec.key, spec.label, *spec.aliases)
        for term in terms:
            term_tokens = _plain_word_tokens(term)
            if not term_tokens:
                continue
            spans.extend(_token_sequence_spans(tokens, term_tokens))
    return spans


def _token_sequence_spans(
    tokens: list[str],
    sequence: list[str],
) -> list[tuple[int, int]]:
    if not sequence or len(sequence) > len(tokens):
        return []
    spans: list[tuple[int, int]] = []
    last_start = len(tokens) - len(sequence)
    for start in range(last_start + 1):
        end = start + len(sequence)
        if tokens[start:end] == sequence:
            spans.append((start, end - 1))
    return spans


def _negative_support_claim_positions(tokens: list[str]) -> set[int]:
    positions: set[int] = set()
    negative_words = {"not", "never", "unsupported", "unavailable"}
    support_words = {"allowed", "available", "executable", "runnable", "supported"}
    action_words = {"execute", "run", "use"}
    blocking_words = {"cannot", "cant"}
    for index, token in enumerate(tokens):
        if token in {"unsupported", "unavailable"}:
            positions.add(index)
            continue
        previous = set(tokens[max(0, index - 3) : index])
        if token in support_words and previous.intersection(negative_words):
            positions.add(index)
            continue
        if token in action_words and previous.intersection(blocking_words):
            positions.add(index)
    return positions


def _context_curiosity_fact_packet(focus: ContextQuestionFocus) -> str:
    facts = {
        "macro_context": (
            "Macro context can frame historical explanations and regime questions "
            "such as inflation, rates, employment, recession indicators, and risk "
            "backdrop. It is contextual only and cannot alter simulation truth or "
            "become a trade signal. Good next steps are choosing a symbol/strategy "
            "and comparing historical periods the user names. Allowed next steps: "
            "ask the user to choose a symbol, strategy, and date windows; compare "
            "buy-and-hold, recurring buys, or supported indicator rules across "
            "those user-chosen windows."
        ),
        "corporate_events": (
            "Corporate actions can provide symbol/date-scoped event context such "
            "as splits and dividends around an equity run. They are valid context "
            "for understanding what was happening around a historical period. They "
            "are not direct event-trading rules, and they cannot rewrite completed "
            "explanations or alter simulation truth. Good next steps are choosing "
            "an equity symbol and date range, then testing a supported strategy "
            "through that period. Allowed next steps: ask for an equity symbol and "
            "date range around an event; test buy-and-hold, recurring buys, or a "
            "supported indicator rule through the period. Do not propose earnings "
            "plays, merger trades, event prediction, volume-impact models, or direct "
            "event-driven rules."
        ),
        "market_movers": (
            "Movers and most-actives context is very short-lived and narrow. It is "
            "not a generic product feed, but it can help the user pick a current "
            "symbol seed for a historical experiment. If a current movers packet is "
            "available, you may mention up to five provided symbols as possible test "
            "seeds, never as recommendations, and make clear that Argus will validate "
            "the selected symbol before any run. Good next steps are choosing one "
            "symbol or date window the user is curious about, then testing buy and "
            "hold, recurring buys, or a supported indicator rule. Do not turn this "
            "into a dashboard, ranking feed, sector-rotation screen, filter pipeline, "
            "volume-surge test, or volume-spike strategy."
        ),
    }
    return facts[focus]


def _market_movers_packet_fact_text(packet: ContextPacket) -> str:
    gainers: list[str] = []
    losers: list[str] = []
    for fact in packet.facts:
        if fact.kind not in {"market_mover_gainer", "market_mover_loser"}:
            continue
        if not isinstance(fact.value, dict):
            continue
        symbol = str(fact.value.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        formatted = _format_market_mover_symbol(
            symbol=symbol,
            percent_change=fact.value.get("percent_change"),
        )
        if fact.kind == "market_mover_gainer":
            gainers.append(formatted)
        else:
            losers.append(formatted)
    sections = []
    if gainers:
        sections.append(f"current gainers: {', '.join(gainers[:5])}")
    if losers:
        sections.append(f"current losers: {', '.join(losers[:5])}")
    if not sections:
        return (
            "A current movers packet was retrieved, but it contained no usable "
            "symbol facts. Do not fabricate mover symbols."
        )
    retrieved_at = packet.retrieved_at.isoformat()
    return (
        "Short-lived movers packet retrieved at "
        f"{retrieved_at}; { '; '.join(sections) }. Use these only as possible "
        "historical-test seeds, not recommendations, predictions, causal evidence, "
        "or simulation truth. Treat symbols as unvalidated until the user chooses "
        "one and deterministic asset validation confirms it can run."
    )


def _market_movers_packet_symbols(packet: ContextPacket) -> list[str]:
    symbols: list[str] = []
    for fact in packet.facts:
        if fact.kind not in {"market_mover_gainer", "market_mover_loser"}:
            continue
        if not isinstance(fact.value, dict):
            continue
        symbol = str(fact.value.get("symbol") or "").strip().upper()
        if symbol:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def _context_answer_respects_live_packet(
    *,
    answer: str | None,
    live_facts: _LiveContextCuriosityFacts,
) -> bool:
    if not live_facts.packet_symbols:
        return True
    return bool(
        answer
        and _mentioned_packet_symbols(
            text=answer,
            symbols=live_facts.packet_symbols,
        )
    )


def _mentioned_packet_symbols(
    *,
    text: str,
    symbols: tuple[str, ...],
) -> list[str]:
    token_map = str.maketrans({char: " " for char in ".,;:!?()[]{}<>\"'`"})
    tokens = {
        token.strip("$").upper()
        for token in text.translate(token_map).split()
        if token.strip("$")
    }
    return [symbol for symbol in symbols if symbol.upper() in tokens]


def _context_packet_grounding_retry_messages(
    *,
    messages: list[dict[str, str]],
    live_facts: _LiveContextCuriosityFacts,
) -> list[dict[str, str]]:
    user_message = messages[-1]
    grounding_message = {
        "role": "system",
        "content": (
            "The previous draft did not use the available short-lived context "
            "packet. Rewrite the answer using at least one provided packet symbol "
            "as an unvalidated historical-test seed. Do not present the packet as "
            "a live dashboard, recommendation, ranking feed, causal proof, or "
            "simulation truth. Keep the user moving toward choosing a symbol and "
            "a supported historical experiment."
        ),
    }
    return [
        *messages[:-1],
        {
            "role": "system",
            "content": (
                "Packet symbols that must ground this answer: "
                f"{', '.join(live_facts.packet_symbols)}"
            ),
        },
        grounding_message,
        user_message,
    ]


def _packet_grounded_context_recovery_answer(
    *,
    focus: ContextQuestionFocus,
    live_facts: _LiveContextCuriosityFacts,
    language: str,
) -> str:
    if focus == "market_movers" and live_facts.packet_symbols:
        seeds = _join_context_symbols(live_facts.packet_symbols[:5])
        return recovery_message(
            "context_market_movers_seed_recovery",
            language=language,
            seeds=seeds,
        )
    return _context_curiosity_recovery_answer(focus, language=language)


def _join_context_symbols(symbols: tuple[str, ...]) -> str:
    if not symbols:
        return "a symbol you choose"
    if len(symbols) == 1:
        return symbols[0]
    return f"{', '.join(symbols[:-1])}, or {symbols[-1]}"


def _format_market_mover_symbol(*, symbol: str, percent_change: Any) -> str:
    if percent_change in (None, ""):
        return symbol
    if isinstance(percent_change, int | float):
        return f"{symbol} ({percent_change:+g}%)"
    text = str(percent_change).strip()
    if not text:
        return symbol
    if text.endswith("%"):
        return f"{symbol} ({text})"
    return f"{symbol} ({text}%)"


def _context_curiosity_recovery_answer(
    focus: ContextQuestionFocus,
    *,
    language: str,
) -> str:
    if focus == "macro_context":
        return recovery_message("context_macro_recovery", language=language)
    if focus == "corporate_events":
        return recovery_message("context_corporate_events_recovery", language=language)
    return recovery_message("context_market_movers_recovery", language=language)


def _llm_composition_unavailable_recovery_answer(*, language: str) -> str:
    return recovery_message("interpreter_unavailable", language=language)


def _route_contextual_money_answer(
    *,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> tuple[StrategySummary, dict[str, Any]]:
    requested_field = str(selected_thread_metadata.get("requested_field") or "")
    if requested_field not in {"initial_capital", "capital_amount", "assumption"}:
        return strategy, {}
    if strategy.capital_amount is None:
        return strategy, {}
    if executable_strategy_type(strategy) == "dca_accumulation":
        return strategy, {}
    updated = strategy.model_copy(deep=True)
    initial_capital = updated.capital_amount
    updated.capital_amount = None
    return updated, {"initial_capital": initial_capital}

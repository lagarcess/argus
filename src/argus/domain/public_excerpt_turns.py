"""One eligibility and privacy projection for every selected public turn."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Any, get_args
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from pydantic import ValidationError

from argus.api.public_excerpt_fact_schemas import (
    PublicExcerptFactBank,
    ReceiptConfig,
    ReceiptCosts,
    ReceiptDates,
    ReceiptFigures,
    ReceiptParameters,
    ReceiptStrategy,
)
from argus.api.public_excerpt_schemas import (
    PublicExcerptBacktestTurn,
    PublicExcerptOfferedNextStep,
    PublicExcerptResearchSource,
    PublicExcerptResearchTurn,
)
from argus.api.schemas import Message
from argus.domain.backtest_message_projection import result_fact_bank
from argus.domain.capability_registry import ALLOWED_TEMPLATES, SUPPORTED_STRATEGY_TYPES
from argus.domain.public_excerpts import (
    _CONTROL_CHARS,
    _SECRET_SHAPED_RE,
    PublicExcerptSanitizationError,
    PublicExcerptSourceError,
    _assumptions,
    _strategy_facts,
    _visual,
    audit_public_excerpt_document,
)
from argus.domain.research.contracts import QuestionShape
from argus.domain.result_figures import with_result_figures

_TEXT_LIMITS = {"question": 500, "answer": 4000, "owner_note": 280}
_BARE_URL = re.compile(r"(?:https?://|www\.)[^\s<>\[\]\"']+", re.IGNORECASE)


def refuse(reason: str, field: str | None = None) -> None:
    raise PublicExcerptSourceError(reason, reason=reason, field=field)


def audit_text(value: object, *, field: str, private_ids: tuple[str, ...]) -> str | None:
    if value is None and field == "owner_note":
        return None
    if not isinstance(value, str):
        refuse("unsafe_text", field)
    assert isinstance(value, str)
    if field != "answer":
        value = " ".join(
            "".join(
                " " if unicodedata.category(c) in _CONTROL_CHARS else c for c in value
            ).split()
        )
    elif any(
        unicodedata.category(c) in _CONTROL_CHARS and c not in "\n\r\t" for c in value
    ):
        refuse("unsafe_text", field)
    if not value.strip():
        if field == "owner_note":
            return None
        refuse("missing_question" if field == "question" else "unsafe_text", field)
    if len(value) > _TEXT_LIMITS[field]:
        refuse("text_too_long", field)
    if _SECRET_SHAPED_RE.search(value):
        refuse("unsafe_text", field)
    try:
        audit_public_excerpt_document({field: value}, private_ids=private_ids)
    except PublicExcerptSanitizationError:
        refuse("unsafe_text", field)
    return value


class _HTMLDestinations(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.urls.update(
            value for key, value in attrs if key in {"href", "src"} and value
        )


def answer_destinations(answer: str) -> set[str]:
    """Resolve actual CommonMark links and scan only unlinked prose for URLs."""
    destinations: set[str] = set()

    def visit(tokens: list[Any]) -> None:
        inside_link = False
        for token in tokens:
            if token.type == "link_open":
                inside_link = True
            elif token.type == "link_close":
                inside_link = False
            for name in ("href", "src"):
                value = token.attrGet(name)
                if value:
                    destinations.add(value)
            if (
                token.type in {"text", "code_inline", "fence", "code_block"}
                and not inside_link
            ):
                for match in _BARE_URL.finditer(token.content):
                    value = match.group().rstrip(".,;:!?")
                    while value.endswith(")") and value.count(")") > value.count("("):
                        value = value[:-1]
                    destinations.add(value)
            if token.children:
                visit(token.children)

    visit(MarkdownIt("commonmark").parse(answer))
    html = _HTMLDestinations()
    html.feed(answer)
    destinations.update(html.urls)
    return destinations


def audit_cited_answer(
    *,
    answer: str | None,
    sources: list[PublicExcerptResearchSource],
    private_ids: tuple[str, ...],
) -> str | None:
    """One citation/privacy boundary for sidecars and declared cited answers."""
    if not sources:
        refuse("missing_sources", "sources")
    text = (
        audit_text(answer, field="answer", private_ids=private_ids)
        if answer is not None
        else None
    )
    try:
        for source in sources:
            parsed = urlsplit(source.url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.netloc.lower() != source.domain.lower()
            ):
                refuse("invalid_source", "sources")
            audit_public_excerpt_document(
                source.model_dump(mode="json"), private_ids=private_ids
            )
    except (ValueError, PublicExcerptSanitizationError) as error:
        if isinstance(error, PublicExcerptSourceError):
            raise
        refuse("invalid_source", "sources")
    if text is not None and answer_destinations(text) - {
        source.url for source in sources
    }:
        refuse("unlisted_url", "answer")
    return text


def _offered_step(metadata: dict[str, Any]) -> PublicExcerptOfferedNextStep | None:
    block = metadata.get("next_experiments")
    rows = block.get("rows") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") not in get_args(
            PublicExcerptOfferedNextStep.model_fields["kind"].annotation
        ):
            continue
        parts = row.get("label_parts")
        if not isinstance(parts, list):
            continue
        symbols = list(
            dict.fromkeys(
                part["value"]
                for part in parts
                if isinstance(part, dict)
                and part.get("type") == "ticker"
                and isinstance(part.get("value"), str)
            )
        )
        if 1 <= len(symbols) <= 5:
            return PublicExcerptOfferedNextStep(kind=row["kind"], symbols=symbols)
    return None


def project_research_turn(
    *,
    message: Message,
    question: str,
    owner_note: str | None,
    language: str,
    private_ids: tuple[str, ...],
) -> PublicExcerptResearchTurn:
    metadata = message.metadata or {}
    source = metadata.get("research")
    if (
        not isinstance(source, dict)
        or source.get("schema_version") != "argus_research/v1"
    ):
        refuse("unsupported_turn")
    if source.get("shape") not in set(get_args(QuestionShape)) - {"fast"}:
        refuse("unsupported_shape")
    if source.get("degraded"):
        refuse("degraded")
    if not source.get("sources"):
        refuse("missing_sources", "sources")
    question = audit_text(question, field="question", private_ids=private_ids)
    answer = audit_text(message.content, field="answer", private_ids=private_ids)
    note = audit_text(owner_note, field="owner_note", private_ids=private_ids)
    try:
        sources = [
            PublicExcerptResearchSource.model_validate(row) for row in source["sources"]
        ]
        assert answer is not None
        answer = audit_cited_answer(
            answer=answer, sources=sources, private_ids=private_ids
        )
        payload = PublicExcerptResearchTurn(
            question=question,
            answer=answer,
            sources=sources,
            retrieved_at=source.get("retrieved_at"),
            anchor_symbols=source.get("anchor_symbols", []),
            asset_class=source.get("asset_class"),
            offered_next_step=_offered_step(metadata),
            owner_note=note,
            content_language=language,
        )
        audit_public_excerpt_document(
            payload.model_dump(mode="json"), private_ids=private_ids
        )
        return payload
    except (
        ValidationError,
        PublicExcerptSanitizationError,
        TypeError,
        ValueError,
    ) as error:
        if isinstance(error, PublicExcerptSourceError):
            raise
        refuse("invalid_source", "sources")


def _subset(value: object, model: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {key: source[key] for key in model.model_fields if key in source}


def _require_complete_figures(
    facts: PublicExcerptFactBank, metrics: dict[str, Any]
) -> None:
    config = facts.config_snapshot
    named_benchmark = any(
        name is not None and name.strip()
        for name in (
            facts.benchmark_symbol,
            config.benchmark_symbol,
            config.resolved_parameters.benchmark_symbol
            if config.resolved_parameters
            else None,
            config.parameters.benchmark_symbol if config.parameters else None,
        )
    )
    required = ["total_return_pct"]
    if named_benchmark:
        required.extend(("benchmark_return_pct", "delta_vs_benchmark_pct"))
        if facts.figures.benchmark_comparison_claim in (None, "unknown"):
            refuse("unsupported_backtest")
    if any(getattr(facts.figures, key) is None for key in required):
        refuse("unsupported_backtest")
    # Private display projection tolerates old strings and coerces booleans.
    # Publishing requires typed source numbers, using the existing closed model.
    aggregate = metrics.get("aggregate")
    performance = aggregate.get("performance") if isinstance(aggregate, dict) else None
    if not isinstance(performance, dict):
        refuse("unsupported_backtest")
    ReceiptFigures.model_validate({key: performance.get(key) for key in required})


def project_backtest_turn(
    *,
    run: Any,
    title: str,
    owner_note: str | None,
    language: str,
    private_ids: tuple[str, ...],
) -> PublicExcerptBacktestTurn:
    if run is None or run.status != "completed":
        refuse("not_completed")
    bank = with_result_figures(result_fact_bank(run))
    config = _subset(bank["config_snapshot"], ReceiptConfig)
    if config.get("template") not in ALLOWED_TEMPLATES | SUPPORTED_STRATEGY_TYPES:
        refuse("unsupported_backtest")
    if isinstance(config.get("date_range"), dict):
        config["date_range"] = _subset(config["date_range"], ReceiptDates)
    if not (
        config.get("date_range") or (config.get("start_date") and config.get("end_date"))
    ):
        refuse("unsupported_backtest")
    # Copy owned typed config fields. Never derive another strategy or metric.
    for key, model in (
        ("resolved_strategy", ReceiptStrategy),
        ("resolved_parameters", ReceiptParameters),
        ("parameters", ReceiptParameters),
    ):
        if key in config:
            config[key] = _subset(config[key], model)
    source_card = bank.get("result_card") or {}
    try:
        # Existing receipt completeness checks remain shared. Their legacy text
        # projection is discarded; v2 publishes only the card's typed facts.
        has_rule_spec = any(
            isinstance(config.get(key), dict) and config[key].get("rule_spec")
            for key in ("resolved_strategy", "resolved_parameters", "parameters")
        )
        if not has_rule_spec:
            _strategy_facts(run.config_snapshot)
        _assumptions(run.config_snapshot, benchmark_symbol=run.benchmark_symbol)
        facts = PublicExcerptFactBank(
            symbols=bank["symbols"],
            asset_class=bank["asset_class"],
            benchmark_symbol=bank["benchmark_symbol"],
            config_snapshot=config,
            figures=bank.get("figures") or {},
            result_card={
                "execution_costs": _subset(source_card["execution_costs"], ReceiptCosts)
            }
            if source_card.get("execution_costs")
            else {},
        )
        _require_complete_figures(facts, bank["metrics"])
        payload = PublicExcerptBacktestTurn(
            idea_title=audit_text(title, field="question", private_ids=private_ids),
            fact_bank=facts,
            visual=_visual(run.chart),
            owner_note=audit_text(
                owner_note, field="owner_note", private_ids=private_ids
            ),
            content_language=language,
        )
        audit_public_excerpt_document(
            payload.model_dump(mode="json"), private_ids=private_ids
        )
        return payload
    except (ValidationError, PublicExcerptSanitizationError, PublicExcerptSourceError):
        refuse("unsupported_backtest")

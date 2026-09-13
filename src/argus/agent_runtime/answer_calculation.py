"""The answer step owns the math.

An answering model, the research provider or the no-search voicing model,
returns its prose and at most one ``AnswerCalculation``. Each input is held to
its source: a page retrieved for this answer, Argus's own market data for a
current price, the user's words, or an assumption the answer states. The
declaration computes. The prose states figures only as ``{{name}}`` references
filled from the computed card; a reference that does not resolve, a money or
percent figure written outside a reference, or an assumption the prose never
states hands the answer to Argus's own lead. Every guard that changes what the
model wrote records a reason code.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from loguru import logger
from pydantic import ValidationError

from argus.agent_runtime.stages.tool_execution import local_tool_call_patch
from argus.domain.calculations import is_free_calculation
from argus.domain.calculations._shared import (
    MISSING_INPUT_CODE,
    SYMBOL_FIELD,
    UNIT_CURRENCY_KEY,
    UNIT_MULTIPLE_KEY,
    UNIT_PERCENT_KEY,
)
from argus.domain.calculations.answer_request import RUNTIME_ARGUMENTS, AnswerCalculation
from argus.domain.research.contracts import (
    CURRENCY_CODES,
    ResearchSource,
    RetrievedRow,
)
from argus.domain.tool_contracts import (
    TOOL_INPUT_SOURCES_FIELD,
    ToolCall,
    ToolFact,
    ToolFactSource,
    ToolResultCard,
)
from argus.domain.tool_declaration import ToolDeclaration, ToolInvocationError

DEFAULT_CURRENCY = "USD"
CURRENCY_FIELD = "currency"
PRICE_FIELD = "price"
# Message metadata that lets a recompute re-render the prose from its new card.
ANSWER_TEMPLATE_KEY = "answer_text_template"

KIND_UNKNOWN_REASON_CODE = "answer_calculation_kind_unknown"
INPUT_UNDECLARED_REASON_CODE = "answer_input_undeclared"
PAGE_UNCITED_REASON_CODE = "answer_input_page_uncited"
MARKET_PRICE_UNAVAILABLE_REASON_CODE = "answer_market_price_unavailable"
MARKET_DATA_NOT_A_PRICE_REASON_CODE = "answer_market_data_not_a_price"
CURRENCY_MISMATCH_REASON_CODE = "calculation_input_currency_mismatch"
CURRENCY_DEFAULTED_REASON_CODE = "calculation_currency_defaulted"
FIGURE_CHECK_REASON_CODE = "answer_figures_replaced"
# Recorded, never replacing anything, when an answer's prose states a figure in
# digits that is neither a cited row nor a value of its calculation.
UNSOURCED_FIGURE_REASON_CODE = "answer_figures_unsourced"

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_REFERENCE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
_WRITTEN_CURRENCY = re.compile(
    r"(?:\b([A-Z]{3})|[A-Z]{0,3}\$|€|£)\s?(\{\{\s*([a-z][a-z0-9_]*)\s*\}\})"
)
_WRITTEN_UNIT_AFTER = re.compile(
    r"(\{\{\s*([a-z][a-z0-9_]*)\s*\}\})\s?([A-Z]{3}\b|%|x\b)"
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_PERCENT_FIGURE = re.compile(r"\d\s?%")
_SYMBOL_MONEY = re.compile(r"(?:[A-Z]{0,3}\$|€|£)\s?\d")
_CODE_MONEY = re.compile(r"\b([A-Z]{3})\s?\d|\d\s?([A-Z]{3})\b")
_MARKET_WINDOW_DAYS = 14

MarketClose = Callable[[str], tuple[float, str] | None]


@dataclass
class ResolvedCalculation:
    """A request held to its sources, as the declaration's arguments."""

    declaration: ToolDeclaration
    arguments: dict[str, Any]
    user_owed: list[str] = field(default_factory=list)
    not_looked_up: list[str] = field(default_factory=list)
    assumed: list[str] = field(default_factory=list)

    @property
    def computable(self) -> bool:
        return not self.user_owed and not self.not_looked_up


@dataclass(frozen=True)
class PublishedCalculation:
    """What an answer publishes: the card patch and prose, the template a
    recompute re-renders, the one figure to ask for, or what was not found."""

    patch: dict[str, Any]
    answer_text: str | None
    template: dict[str, str] | None
    question_field: str | None
    not_looked_up: tuple[str, ...]
    owed: tuple[str, ...] = ()


def publish_calculation(
    request: AnswerCalculation,
    *,
    template: str,
    language: str,
    catalog: Any,
    retrieved: Sequence[ResearchSource],
    currency: str | None,
    subject_symbol: str | None,
    market_close: MarketClose,
    notes: list[str],
    evidence: Sequence[RetrievedRow] = (),
) -> PublishedCalculation | None:
    """The card and prose for an answer's request, or None for an unknown kind."""
    resolved = resolve_calculation(
        request,
        catalog=catalog,
        retrieved=retrieved,
        currency=currency,
        subject_symbol=subject_symbol,
        market_close=market_close,
        notes=notes,
        evidence=evidence,
    )
    if resolved is None:
        return None
    if not resolved.computable:
        return PublishedCalculation(
            patch={},
            answer_text=None,
            template=None,
            question_field=resolved.user_owed[0] if resolved.user_owed else None,
            not_looked_up=tuple(resolved.not_looked_up),
            owed=tuple(resolved.user_owed),
        )
    patch = computed_answer_patch(resolved)
    card = card_in(patch)
    succeeded = card.outcome.status == "succeeded"
    driving = {fact.name for fact in card.presentation.inputs if fact.driving}
    text, failure = render_answer_text(
        template,
        card,
        assumed=[name for name in resolved.assumed if name in driving],
    )
    if succeeded and failure is None:
        stored = {"artifact_id": card.artifact_id, "text": template, "language": language}
        return PublishedCalculation(patch, text, stored, None, ())
    _note(
        notes,
        FIGURE_CHECK_REASON_CODE,
        failure=failure,
        status=card.outcome.status,
        unresolved=unresolved_references(template, card),
        references=sorted(set(_REFERENCE.findall(template))),
        card_facts=sorted(_reference_facts(card)),
    )
    return PublishedCalculation(
        patch, fallback_answer_lead(language, succeeded=succeeded), None, None, ()
    )


def resolve_calculation(
    request: AnswerCalculation,
    *,
    catalog: Any,
    retrieved: Sequence[ResearchSource],
    currency: str | None,
    subject_symbol: str | None,
    market_close: MarketClose,
    notes: list[str],
    evidence: Sequence[RetrievedRow] = (),
) -> ResolvedCalculation | None:
    declaration = catalog.get(request.kind)
    if declaration is None or not is_free_calculation(declaration):
        _note(notes, KIND_UNKNOWN_REASON_CODE, kind=request.kind)
        return None
    declared = set(declaration.arguments_type.model_fields) - RUNTIME_ARGUMENTS
    pages = {source.url: source for source in retrieved}
    counted_in = _calculation_currency(request, currency, notes)
    arguments: dict[str, Any] = {CURRENCY_FIELD: counted_in}
    symbol = _stated_symbol(request) or subject_symbol
    if SYMBOL_FIELD in declared and symbol:
        arguments[SYMBOL_FIELD] = symbol
    sources: dict[str, ToolFactSource] = {}
    resolved = ResolvedCalculation(declaration=declaration, arguments=arguments)
    for item in request.inputs:
        name = item.name
        if name in (CURRENCY_FIELD, SYMBOL_FIELD) or name == request.solve_for:
            continue
        if name not in declared:
            _note(notes, INPUT_UNDECLARED_REASON_CODE, name=name)
            continue
        if item.currency and item.currency.strip().upper() != counted_in:
            resolved.not_looked_up.append(name)
            _note(notes, CURRENCY_MISMATCH_REASON_CODE, name=name, currency=item.currency)
            continue
        if item.source == "user":
            if item.value is None:
                if not _blank_is_owed(declaration, name):
                    continue
                resolved.user_owed.append(name)
                continue
            arguments[name], sources[name] = item.value, ToolFactSource(kind="user")
        elif item.source == "assumption":
            if item.value is None:
                continue
            arguments[name], sources[name] = item.value, ToolFactSource(kind="assumption")
            resolved.assumed.append(name)
        elif item.source == "market_data":
            price = _market_price(name, symbol, market_close, notes)
            if price is None:
                resolved.not_looked_up.append(name)
                continue
            arguments[name], sources[name] = price
        else:
            page = pages.get(item.source_url or "")
            cited = None if page is not None else _evidenced(item.value, evidence)
            if item.value is None or (page is None and cited is None):
                resolved.not_looked_up.append(name)
                _note(notes, PAGE_UNCITED_REASON_CODE, name=name)
                continue
            arguments[name], sources[name] = (
                item.value,
                (
                    page_source(page, item.as_of)
                    if page is not None
                    else evidence_source(cited, item.as_of)
                ),
            )
    if request.solve_for in declared:
        arguments[request.solve_for] = None
    if sources:
        arguments[TOOL_INPUT_SOURCES_FIELD] = {
            name: source.model_dump(mode="json") for name, source in sources.items()
        }
    if resolved.computable:
        resolved.user_owed.extend(
            _blank_inputs(declaration, arguments, request.solve_for)
        )
    return resolved


def computed_answer_patch(resolved: ResolvedCalculation) -> dict[str, Any]:
    """The card for the resolved inputs, in the execute loop's own patch shape."""
    declaration = resolved.declaration
    call = ToolCall(
        tool_name=declaration.name,
        call_id=f"answer-{uuid4()}",
        arguments=resolved.arguments,
    )
    return local_tool_call_patch(
        declaration=declaration, call=call, artifact_id=str(uuid4())
    )


def card_in(patch: dict[str, Any]) -> ToolResultCard:
    return ToolResultCard.model_validate(
        patch["final_response_payload"]["tool_result_cards"][0]
    )


def render_answer_text(
    template: str, card: ToolResultCard, *, assumed: Sequence[str] = ()
) -> tuple[str, str | None]:
    """The prose with each reference filled from the card, and the check's
    failure code when a figure did not come from the card."""
    facts = _reference_facts(card)
    unresolved: list[str] = []

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        fact = facts.get(name)
        if fact is not None:
            return figure_text(fact)
        stated = _stated_argument(card, name)
        if stated is None:
            unresolved.append(name)
            return match.group(0)
        return stated

    text = _REFERENCE.sub(fill, _without_written_currency(template, facts))
    if unresolved:
        return text, "invalid_figure_reference"
    referenced = set(_REFERENCE.findall(template))
    if any(name not in referenced for name in assumed):
        return text, "assumption_not_stated"
    return text, None


def unresolved_references(template: str, card: ToolResultCard) -> list[str]:
    """The ``{{name}}`` references a card cannot fill, for the guard's record."""
    facts = _reference_facts(card)
    return sorted(
        {
            name
            for name in _REFERENCE.findall(template)
            if name not in facts and _stated_argument(card, name) is None
        }
    )


def figure_text(fact: ToolFact) -> str:
    """A figure as the prose states it: the card's value with its unit."""
    value = fact.value
    if value is None or isinstance(value, (bool, str)):
        return str(value)
    key = fact.unit.locale_key if fact.unit is not None else None
    if key == UNIT_CURRENCY_KEY:
        return f"{_money_code(fact) or ''} {_number(value, money=True)}".strip()
    if key == UNIT_PERCENT_KEY:
        return f"{_number(value)}%"
    if key == UNIT_MULTIPLE_KEY:
        return f"{_number(value)}x"
    return _number(value)


def fallback_answer_lead(language: str, *, succeeded: bool) -> str:
    """Argus's own lead when the prose cannot carry the card's figures."""
    spanish = str(language or "").startswith("es")
    if succeeded:
        if spanish:
            return "Aquí está el cálculo con estos datos. Cambia cualquier dato para recalcularlo."
        return (
            "Here is the calculation from these inputs. Change any input to recompute it."
        )
    if spanish:
        return (
            "Los números tal como están no tienen solución. La tarjeta indica qué "
            "falta y ofrece una corrección."
        )
    return "The numbers as stated do not solve. The card names what is missing and offers a fix."


def latest_market_close(symbol: str) -> tuple[float, str] | None:
    """The latest daily close Argus's own market data has for a symbol, and its date."""
    try:
        # Lazy: the compute stack loads only when an answer needs a price.
        from argus.domain.engine import classify_symbol
        from argus.domain.market_data.new_york_clock import new_york_today
        from argus.domain.market_data.provider import fetch_price_series

        asset = classify_symbol(symbol)
        end = new_york_today()
        series = fetch_price_series(
            symbol,
            asset.asset_class,
            end - timedelta(days=_MARKET_WINDOW_DAYS),
            end,
            "1d",
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Answer market close unavailable", symbol=symbol, error=str(exc))
        return None
    closes = [
        (index, float(value))
        for index, value in zip(getattr(series, "index", []), list(series), strict=False)
        if value is not None
    ]
    if not closes:
        return None
    index, close = closes[-1]
    return close, str(index)[:10]


def cited_page_inputs(
    calculation: dict[str, Any] | None,
    sources: Sequence[ResearchSource],
    names: Sequence[str],
) -> dict[str, tuple[Any, dict[str, Any]]]:
    """The named inputs a refreshed answer read from pages it retrieved, each
    with its page source; anything else in the calculation is ignored."""
    if not calculation:
        return {}
    try:
        request = AnswerCalculation.model_validate(calculation)
    except ValidationError:
        return {}
    pages = {source.url: source for source in sources}
    found: dict[str, tuple[Any, dict[str, Any]]] = {}
    for item in request.inputs:
        page = pages.get(item.source_url or "")
        if (
            item.name in names
            and item.source == "page"
            and page
            and item.value is not None
        ):
            found[item.name] = (
                item.value,
                page_source(page, item.as_of).model_dump(mode="json"),
            )
    return found


def _reference_facts(card: ToolResultCard) -> dict[str, ToolFact]:
    presentation = card.presentation
    facts: dict[str, ToolFact] = {
        fact.name: fact for fact in presentation.inputs if fact.value is not None
    }
    facts.update({row.name: row for row in presentation.rows})
    if presentation.answer is not None:
        facts[presentation.answer.name] = presentation.answer
    return facts


def _money_code(fact: ToolFact | None) -> str | None:
    if fact is None or fact.unit is None or fact.unit.locale_key != UNIT_CURRENCY_KEY:
        return None
    return str(fact.unit.interpolation_args.get("code") or "").strip() or None


def _without_written_currency(template: str, facts: dict[str, ToolFact]) -> str:
    """A reference renders with its own unit, so a currency the prose wrote just
    before or after a money reference, or a % or x written after a percent or
    multiple reference, is not stated twice."""

    def drop(match: re.Match[str]) -> str:
        code = _money_code(facts.get(match.group(3)))
        if code is None or (match.group(1) and match.group(1) != code):
            return match.group(0)
        return match.group(2)

    def drop_after(match: re.Match[str]) -> str:
        fact = facts.get(match.group(2))
        unit = match.group(3)
        key = fact.unit.locale_key if fact is not None and fact.unit is not None else None
        if (
            (fact is not None and unit == _money_code(fact))
            or (unit == "%" and key == UNIT_PERCENT_KEY)
            or (unit == "x" and key == UNIT_MULTIPLE_KEY)
        ):
            return match.group(1)
        return match.group(0)

    return _WRITTEN_UNIT_AFTER.sub(drop_after, _WRITTEN_CURRENCY.sub(drop, template))


def render_offer_prose(template: str, card: ToolResultCard) -> tuple[str, int]:
    """The prose of an offered calculation: references to figures the card holds
    filled, and each sentence or table row that leans on a result the offer
    cannot show left out. Returns the text and how many were left out."""
    facts = _reference_facts(card)

    def fill(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        if fact is not None:
            return figure_text(fact)
        stated = _stated_argument(card, match.group(1))
        return stated if stated is not None else match.group(0)

    filled = _REFERENCE.sub(fill, _without_written_currency(template, facts))
    kept: list[str] = []
    dropped = 0
    for line in filled.split("\n"):
        if "{{" not in line:
            kept.append(line)
            continue
        if line.lstrip().startswith("|"):
            dropped += 1
            continue
        sentences = _SENTENCE_BREAK.split(line)
        remaining = [sentence for sentence in sentences if "{{" not in sentence]
        dropped += len(sentences) - len(remaining)
        if remaining:
            kept.append(" ".join(remaining))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip(), dropped


def _stated_argument(card: ToolResultCard, name: str) -> str | None:
    """A declared input the card holds as text rather than as a figure, such as a
    start date or a choice, stated as the card received it."""
    value = card.arguments.get(name)
    return value if isinstance(value, str) and value.strip() else None


def states_a_figure(text: str) -> bool:
    """A money or percent figure written as digits rather than referenced."""
    if _PERCENT_FIGURE.search(text) or _SYMBOL_MONEY.search(text):
        return True
    return any(
        (match.group(1) or match.group(2)) in CURRENCY_CODES
        for match in _CODE_MONEY.finditer(text)
    )


def _number(value: float, *, money: bool = False) -> str:
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return f"{int(rounded):,}"
    if money:
        return f"{rounded:,.2f}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def _calculation_currency(
    request: AnswerCalculation, currency: str | None, notes: list[str]
) -> str:
    stated = next(
        (
            str(item.value).strip().upper()
            for item in request.inputs
            if item.name == CURRENCY_FIELD and isinstance(item.value, str)
        ),
        "",
    )
    if stated in CURRENCY_CODES:
        return stated
    if currency:
        return currency.strip().upper()
    _note(notes, CURRENCY_DEFAULTED_REASON_CODE, currency=DEFAULT_CURRENCY)
    return DEFAULT_CURRENCY


def _stated_symbol(request: AnswerCalculation) -> str | None:
    return next(
        (
            item.value.strip()
            for item in request.inputs
            if item.name == SYMBOL_FIELD
            and isinstance(item.value, str)
            and item.value.strip()
        ),
        None,
    )


def _market_price(
    name: str, symbol: str | None, market_close: MarketClose, notes: list[str]
) -> tuple[float, ToolFactSource] | None:
    if name != PRICE_FIELD:
        _note(notes, MARKET_DATA_NOT_A_PRICE_REASON_CODE, name=name)
        return None
    close = market_close(symbol) if symbol else None
    if close is None:
        _note(notes, MARKET_PRICE_UNAVAILABLE_REASON_CODE, symbol=symbol)
        return None
    value, as_of = close
    dated = as_of if _ISO_DATE.fullmatch(as_of or "") else None
    return value, ToolFactSource(kind="market_data", date=dated)


def page_source(page: ResearchSource, as_of: str | None) -> ToolFactSource:
    dated = next(
        (
            value[:10]
            for value in (as_of, page.source_date)
            if value and _ISO_DATE.fullmatch(value[:10])
        ),
        None,
    )
    title = page.title.strip() or urlparse(page.url).hostname or ""
    return ToolFactSource(
        kind="page", title=title[:300] or None, url=page.url[:2048], date=dated
    )


def _evidenced(value: Any, evidence: Sequence[RetrievedRow]) -> RetrievedRow | None:
    """The cited row stating this input's figure, when the page it names is the
    provider's own finance data, whose citation keeps no URL."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return next(
        (
            row
            for row in evidence
            if abs(float(row.value) - float(value))
            <= max(abs(float(row.value)) * 1e-6, 1e-9)
        ),
        None,
    )


def evidence_source(row: RetrievedRow | None, as_of: str | None) -> ToolFactSource:
    """A figure cited from finance data names its subject and date, never a URL."""
    assert row is not None
    dated = next(
        (
            value[:10]
            for value in (as_of, row.as_of)
            if value and _ISO_DATE.fullmatch(value[:10])
        ),
        None,
    )
    title = f"{row.subject} {row.label}".strip()
    return ToolFactSource(kind="page", title=title[:300] or None, date=dated)


def _blank_is_owed(declaration: ToolDeclaration, name: str) -> bool:
    """A blank is owed by the user when the kind needs it: a required input or
    one of a rule's blanks. An optional detail left blank keeps its default."""
    field = declaration.arguments_type.model_fields.get(name)
    in_rule = any(name in rule.fields for rule in declaration.rules)
    return field is None or field.is_required() or in_rule


def _blank_inputs(
    declaration: ToolDeclaration, arguments: dict[str, Any], solve_for: str | None
) -> list[str]:
    """Inputs the declaration still needs, other than the one being solved."""
    try:
        declaration.validate_arguments(arguments)
    except ToolInvocationError as exc:
        failure = exc.outcome.failure
        if failure is None:
            return []
        if failure.code == MISSING_INPUT_CODE:
            return list(failure.fields)
        if failure.code == "exactly_one_unknown":
            return [
                name
                for name in failure.fields
                if arguments.get(name) is None and name != solve_for
            ]
        return []
    except ValidationError as exc:
        return [
            str(error["loc"][0])
            for error in exc.errors()
            if error.get("type") == "missing" and error.get("loc")
        ]
    except (ValueError, TypeError):
        return []
    outcome = declaration.invoke_sync(arguments)
    if outcome.failure is not None and outcome.failure.code == MISSING_INPUT_CODE:
        return list(outcome.failure.fields)
    return []


def _note(notes: list[str], code: str, **context: Any) -> None:
    if code not in notes:
        notes.append(code)
    logger.info(
        "Answer calculation guard {} {}", code, context, failure_classification=code
    )


_PROSE_FIGURE = re.compile(
    r"(?<![\w/.,-])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(%|x\b)?"
    r"(?:\s+(billion|bn|million|thousand|mil millones|millones|mil))?(?![\w/-])"
)
_SCALES = {
    "billion": 1e9,
    "bn": 1e9,
    "mil millones": 1e9,
    "million": 1e6,
    "millones": 1e6,
    "thousand": 1e3,
    "mil": 1e3,
}


def _figure_value(token: str) -> tuple[float, int]:
    """The number a digit token states and its shown decimals, for either
    decimal separator."""
    last_dot, last_comma = token.rfind("."), token.rfind(",")
    decimal = "." if last_dot > last_comma else ","
    whole, _, fraction = token.rpartition(decimal)
    if (
        not whole
        or len(fraction) == 3
        and token.count(decimal) >= 1
        and (token.count(decimal) > 1 or last_dot > -1 and last_comma > -1 or not whole)
    ):
        whole, fraction = token, ""
    if (
        fraction
        and len(fraction) == 3
        and "." not in token.replace(decimal, "", 1)
        and "," not in token.replace(decimal, "", 1)
    ):
        # One separator followed by three digits reads as a thousands group.
        whole, fraction = token, ""
    digits = "".join(ch for ch in whole if ch.isdigit())
    number = float(digits or 0) + (float(f"0.{fraction}") if fraction.isdigit() else 0.0)
    return number, len(fraction) if fraction.isdigit() else 0


def unsourced_prose_figures(
    prose: str,
    *,
    cited: Sequence[float],
    cards: Sequence[ToolResultCard],
    names: Sequence[str] = (),
) -> list[str]:
    """The digit figures an answer's prose states that match neither a cited row
    nor a value of its calculation. Dates, years, a day number beside its year,
    numbers inside words and a number that names a cited product or a named
    model are not figures."""
    named = {
        token
        for text in names
        for token in re.findall(r"(?<![\d.,])\d+(?![\d.,])", str(text))
    }
    known = [float(value) for value in cited]
    for card in cards:
        presentation = card.presentation
        facts = [*presentation.inputs, *presentation.rows]
        if presentation.answer is not None:
            facts.append(presentation.answer)
        known.extend(
            float(fact.value)
            for fact in facts
            if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool)
        )
    text = _ISO_DATE.sub(" ", prose)
    unsourced: list[str] = []
    for match in _PROSE_FIGURE.finditer(text):
        token, suffix, scale = match.group(1), match.group(2), match.group(3)
        plain = not suffix and not scale and token.isdigit()
        if plain and re.fullmatch(r"(19|20)\d{2}", token):
            continue
        if plain and (token in named or _names_a_model(text, match.start())):
            continue
        if (
            plain
            and len(token) <= 2
            and _YEAR.search(text, match.end(), match.end() + 25)
        ):
            continue
        value, decimals = _figure_value(token)
        candidates = [value, value * _SCALES.get(str(scale or "").lower(), 1.0)]
        if any(
            abs(candidate - item) <= max(abs(item) * 0.005, 0.5 * 10**-decimals)
            for candidate in candidates
            for item in known
        ):
            continue
        unsourced.append(match.group(0).strip())
    return unsourced


def _names_a_model(text: str, start: int) -> bool:
    """A bare number right after a mid-sentence word that mixes capitals and
    lowercase, such as Porsche 911 or iPhone 16, names a model."""
    word = re.search(r"([^\W\d_]+) $", text[:start])
    if word is None:
        return False
    letters = word.group(1)
    if not (any(ch.isupper() for ch in letters) and any(ch.islower() for ch in letters)):
        return False
    before = text[: word.start(1)].rstrip()
    return bool(before) and before[-1] not in ".!?:\n"


def record_unsourced_figures(
    prose: str,
    *,
    cited: Sequence[float],
    cards: Sequence[ToolResultCard],
    notes: list[str],
    message: str,
    names: Sequence[str] = (),
) -> int:
    """Records, and never replaces, the figures an answer states with no source."""
    figures = unsourced_prose_figures(prose, cited=cited, cards=cards, names=names)
    if figures:
        if UNSOURCED_FIGURE_REASON_CODE not in notes:
            notes.append(UNSOURCED_FIGURE_REASON_CODE)
        logger.info(
            "Answer prose figures with no cited row or calculation value "
            "count={} figures={} question={}",
            len(figures),
            figures[:20],
            " ".join(str(message).split())[:160],
            failure_classification=UNSOURCED_FIGURE_REASON_CODE,
        )
    return len(figures)


def cards_in(patch: dict[str, Any] | None) -> list[ToolResultCard]:
    """Every card a computed patch carries."""
    payload = (patch or {}).get("final_response_payload") or {}
    return [
        ToolResultCard.model_validate(card)
        for card in payload.get("tool_result_cards") or []
    ]

"""Published inputs for a calculation: retrieved as typed rows, computed by the declaration.

Decision 10 answered a forward-looking question with the retrieval model's
own arithmetic. Now the model retrieves the inputs a declared calculation
names, one typed row each with the page it was read from and its date, and
the valuation math computes the figures; the card carries each input with its
source. Nothing here reads prose: a row feeds an input only when its label is
that input's name, the vocabulary the retrieval ask spells out.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from loguru import logger

from argus.agent_runtime.interpreter.calculation_request import (
    RUNTIME_ARGUMENTS,
    CalculationRequest,
)
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.stages.tool_execution import local_tool_call_patch
from argus.domain.calculations._shared import SYMBOL_FIELD
from argus.domain.research.contracts import ResearchPacket, RetrievedRow
from argus.domain.tool_contracts import TOOL_INPUT_SOURCES_FIELD, ToolCall, ToolFactSource
from argus.domain.tool_declaration import ToolDeclaration

# Recorded on the interpretation when a scenario read carried no calculation
# and the valuation declaration was chosen for it.
SCENARIO_CALCULATION_DEFAULTED_REASON_CODE = "scenario_calculation_defaulted"
SCENARIO_DEFAULT_KIND = "valuation_scenarios"
# Recorded when a retrieved money row is counted in another currency than the
# calculation, so the input stays blank for the reader to type.
CURRENCY_MISMATCH_REASON_CODE = "calculation_input_currency_mismatch"
CURRENCY_FIELD = "currency"
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# What each retrievable input means, by kind, in the words the retrieval ask
# uses. Only kinds with inputs a page states appear; every name is checked
# against its declaration by test.
RETRIEVAL_MEANINGS: dict[str, dict[str, str]] = {
    "valuation_scenarios": {
        "price": "the current share price",
        "per_share": (
            "earnings per share for the trailing twelve months, or the next "
            "fiscal year when that is what pages publish"
        ),
        "growth_base_pct": (
            "the consensus published forecast of yearly earnings growth, as a percent"
        ),
        "growth_low_pct": (
            "the lowest published forecast of yearly earnings growth, as a percent"
        ),
        "growth_high_pct": (
            "the highest published forecast of yearly earnings growth, as a percent"
        ),
        "multiple_base": (
            "the price-to-earnings multiple a page states as fair or forward"
        ),
        "multiple_low": "the low end of a published price-to-earnings range",
        "multiple_high": "the high end of a published price-to-earnings range",
    },
    "time_value": {
        "present_value": (
            "the current price of the item or loan the question names, in the "
            "question's currency"
        ),
        "future_value": (
            "the current price of the goal the question names, in the question's "
            "currency"
        ),
        "annual_rate_pct": (
            "the published yearly rate for the loan, deposit or product the "
            "question names, as a percent"
        ),
    },
    "effective_rate": {
        "nominal_rate_pct": (
            "the published nominal yearly rate for the product the question "
            "names, as a percent"
        ),
    },
    "price_multiple": {
        "price": "the current share price",
        "per_share": "earnings per share for the trailing twelve months",
        "multiple": "the current price-to-earnings multiple",
    },
    "income_yield": {
        "price": "the current share price",
        "annual_income": "the yearly dividend per share",
        "yield_pct": "the current dividend yield, as a percent",
    },
    "growth_projection": {
        "annual_rate_pct": "a published forecast of yearly growth or return, as a percent",
        "inflation_rate_pct": (
            "the latest published yearly inflation rate where the reader lives, "
            "as a percent"
        ),
    },
    "discounted_cash_flow": {
        "cash_flow": "free cash flow per share for the trailing twelve months",
        "growth_rate_pct": (
            "the consensus published forecast of yearly growth, as a percent"
        ),
        "discount_rate_pct": (
            "a published required return or cost of equity, as a percent"
        ),
    },
    "bond_value": {
        "coupon_rate_pct": "the coupon rate, as a percent",
        "yield_to_maturity_pct": "the yield to maturity, as a percent",
        "price": "the current price per 100 of face value",
    },
    "expense_ratio": {
        "ratio_pct": "the fund's expense ratio, as a percent",
    },
}


def retrievable(read: CalculationRequest | None) -> bool:
    """Whether a read names an input a published page can supply for its kind."""
    if read is None or read.kind not in RETRIEVAL_MEANINGS:
        return False
    meanings = RETRIEVAL_MEANINGS[str(read.kind)]
    return any(name in meanings for name in read.retrieve)


def scenario_calculation(interpretation: StructuredInterpretation) -> CalculationRequest:
    """The calculation a scenario turn computes: the model's read, or the
    valuation declaration when the read carried none (recorded)."""
    read = interpretation.calculation
    if read is not None and read.kind in RETRIEVAL_MEANINGS:
        return read
    if SCENARIO_CALCULATION_DEFAULTED_REASON_CODE not in interpretation.reason_codes:
        interpretation.reason_codes.append(SCENARIO_CALCULATION_DEFAULTED_REASON_CODE)
        logger.info(
            "Scenario computed by the default declaration, the read carried none"
            f" read_kind={getattr(read, 'kind', None)}",
            failure_classification=SCENARIO_CALCULATION_DEFAULTED_REASON_CODE,
        )
    return CalculationRequest(
        kind=SCENARIO_DEFAULT_KIND,
        inputs=dict(read.inputs) if read is not None else {},
        retrieve=list(RETRIEVAL_MEANINGS[SCENARIO_DEFAULT_KIND]),
    )


def retrieval_inputs(
    request: CalculationRequest, declaration: ToolDeclaration
) -> list[tuple[str, str]]:
    """The inputs the ask names, in the vocabulary's order: the read's own
    ``retrieve`` list when it names any, else every retrievable input the user
    did not state."""
    meanings = RETRIEVAL_MEANINGS.get(declaration.name, {})
    stated = {name for name, value in request.inputs.items() if value is not None}
    wanted = [name for name in request.retrieve if name in meanings] or list(meanings)
    return [
        (name, meanings[name])
        for name in meanings
        if name in wanted and name not in stated
    ]


def arguments_from_rows(
    packet: ResearchPacket,
    request: CalculationRequest,
    declaration: ToolDeclaration,
    *,
    currency: str,
    symbol: str | None,
    interpretation: StructuredInterpretation | None = None,
) -> dict[str, Any]:
    """The declaration's arguments: the user's stated inputs, then one retrieved
    row per named input, each carrying its page and date as its source. A money
    row counted in another currency feeds nothing."""
    declared = set(declaration.arguments_type.model_fields) - RUNTIME_ARGUMENTS
    arguments: dict[str, Any] = {
        name: value
        for name, value in request.inputs.items()
        if name in declared and value is not None
    }
    if SYMBOL_FIELD in declared and symbol and not arguments.get(SYMBOL_FIELD):
        arguments[SYMBOL_FIELD] = symbol
    arguments.setdefault(CURRENCY_FIELD, currency)
    sources: dict[str, dict[str, Any]] = {}
    wanted = {name for name, _ in retrieval_inputs(request, declaration)}
    counted_in = str(arguments[CURRENCY_FIELD]).strip().upper()
    mismatched: list[str] = []
    for row in packet.rows:
        name = row.label.strip().casefold()
        if name not in wanted or name in arguments:
            continue
        if row.kind == "currency" and row.unit.strip().upper() != counted_in:
            mismatched.append(name)
            continue
        arguments[name] = row.value
        sources[name] = _row_source(row).model_dump(mode="json")
    if sources:
        arguments[TOOL_INPUT_SOURCES_FIELD] = sources
    if mismatched:
        if (
            interpretation is not None
            and CURRENCY_MISMATCH_REASON_CODE not in interpretation.reason_codes
        ):
            interpretation.reason_codes.append(CURRENCY_MISMATCH_REASON_CODE)
        logger.info(
            f"Retrieved money inputs in another currency left blank inputs={mismatched} currency={counted_in}",
            failure_classification=CURRENCY_MISMATCH_REASON_CODE,
        )
    return arguments


def computed_scenario_patch(
    declaration: ToolDeclaration, arguments: dict[str, Any]
) -> dict[str, Any]:
    """The card for the retrieved inputs, in the execute loop's own patch shape."""
    call = ToolCall(
        tool_name=declaration.name,
        call_id=f"scenario-{uuid4()}",
        arguments=arguments,
    )
    return local_tool_call_patch(
        declaration=declaration, call=call, artifact_id=str(uuid4())
    )


def _row_source(row: RetrievedRow) -> ToolFactSource:
    title = " ".join(part for part in (row.subject.strip(), row.label.strip()) if part)
    as_of = str(row.as_of or "").strip()
    return ToolFactSource(
        kind="page",
        title=title[:300] or None,
        url=row.source_url,
        date=as_of if _ISO_DATE.fullmatch(as_of) else None,
    )
